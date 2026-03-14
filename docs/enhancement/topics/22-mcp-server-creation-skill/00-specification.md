# MCP Server Creation Skill - Design Specification

**Topic:** #22 - MCP Server Creation Skill  
**Status:** 🟡 PENDING → ✅ DESIGNED  
**Target Version:** v1.7+  
**Date:** 2026-03-17  
**Priority:** Medium  
**Depends On:** Topic #21 (Universal Integration Framework)

---

## Executive Summary

The MCP Server Creation Skill enables users to automatically generate MCP (Model Context Protocol) servers and CLI-Anything commands from external API specifications. Using natural language input, the skill parses REST APIs (OpenAPI) and GraphQL APIs, applies AI-powered semantic enrichment, provides an interactive UI for refinement, and generates production-ready code.

**Key Features:**
- **Natural Language Input** — Users describe what they want in plain English
- **Multi-API Support** — OpenAPI/Swagger and GraphQL introspection
- **AI Semantic Enrichment** — LLM generates meaningful tool names and descriptions
- **Interactive Configuration** — UI for reviewing and refining generated tools
- **Dual Output** — Both downloadable code and immediate runtime registration
- **Three Deployment Modes** — Local runtime, Docker container, or external hosting
- **External Prompt Files** — Maintainable Markdown prompt templates

**Builds On:** Topic #21 (Universal Integration Framework) — Generated servers integrate seamlessly with the adapter registry.

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Architecture Overview](#2-architecture-overview)
3. [Information Extraction](#3-information-extraction)
4. [Semantic Enrichment](#4-semantic-enrichment)
5. [Interactive UI Flow](#5-interactive-ui-flow)
6. [Code Generation](#6-code-generation)
7. [Integration with Universal Framework](#7-integration-with-universal-framework)
8. [Example Scenarios](#8-example-scenarios)
9. [Implementation Phases](#9-implementation-phases)
10. [Database Schema](#10-database-schema)
11. [File Structure](#11-file-structure)
12. [Open Questions](#12-open-questions)

---

## 1. Requirements

### 1.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1 | Accept natural language API descriptions | High |
| FR2 | Parse OpenAPI 3.x specifications | High |
| FR3 | Parse GraphQL schemas via introspection | High |
| FR4 | Auto-detect API type from URL | Medium |
| FR5 | Extract endpoints, parameters, schemas, auth | High |
| FR6 | AI-powered semantic enrichment (LLM) | High |
| FR7 | Interactive UI for tool selection and editing | High |
| FR8 | Generate MCP server code (Python/FastMCP) | High |
| FR9 | Generate CLI-Anything configuration | High |
| FR10 | Generate runtime adapter configuration | High |
| FR11 | Support three deployment modes | Medium |
| FR12 | Register adapters immediately in AgentOS | High |
| FR13 | External prompt files for maintainability | High |
| FR14 | Generate test suites | Medium |

### 1.2 Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR1 | Handle APIs with 1000+ endpoints | High |
| NFR2 | Generation time < 30 seconds | Medium |
| NFR3 | LLM prompts in external Markdown files | High |
| NFR4 | Hot-reload prompts without restart | Medium |
| NFR5 | Backward compatible with existing adapters | High |

### 1.3 Security Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| SR1 | Never log API credentials | High |
| SR2 | Validate file paths in CLI-Anything | High |
| SR3 | Warn about dangerous operations (delete, merge) | Medium |
| SR4 | Mark sensitive APIs (financial, healthcare) | Medium |

---

## 2. Architecture Overview

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MCP SERVER CREATION SKILL                           │
│                           (Topic #22 - This Design)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Natural   │  │ Interactive │  │    Code     │  │     Deployment      │ │
│  │  Language   │──│    UI       │──│ Generation  │──│   & Registration    │ │
│  │    Input    │  │  Review     │  │  (Jinja2)   │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│         │                │                │                │                │
│         ▼                ▼                ▼                ▼                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Core Components                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │   Parser    │  │  Enrichment │  │  Generator  │  │  Registrar  │ │   │
│  │  │  (OpenAPI/  │  │    (LLM)    │  │  (Jinja2)   │  │   (Adapter  │ │   │
│  │  │  GraphQL)   │  │             │  │             │  │   Registry) │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      UNIVERSAL INTEGRATION FRAMEWORK                        │
│                         (Topic #21 - Existing)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    IntegrationRegistry                                │  │
│  └──────────────────┬────────────────────────────────────────────────────┘  │
│                     │                                                       │
│  ┌──────────────────┴──────────────────────────────────────────────────┐   │
│  │              SecureAdapterWrapper                                    │   │
│  └──────────────────┬──────────────────────────────────────────────────┘   │
│                     │                                                       │
│         ┌───────────┼───────────┐                                           │
│         ▼           ▼           ▼                                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                                    │
│  │   MCP    │ │   CLI    │ │ Webhook  │                                    │
│  │  Adapter │ │Anything  │ │  Adapter │                                    │
│  └──────────┘ └──────────┘ └──────────┘                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Workflow

```
User Input: "Create MCP server for GitHub API"
      │
      ▼
┌─────────────────────────────────────────┐
│ Step 1: API Detection & Fetch           │
│ • Detect API type (OpenAPI/GraphQL)     │
│ • Fetch spec from URL                   │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Step 2: Structural Parsing              │
│ • Parse endpoints/queries               │
│ • Extract parameters & schemas          │
│ • Identify auth schemes                 │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Step 3: Semantic Enrichment (LLM)       │
│ • Generate semantic tool names          │
│ • Suggest logical groupings             │
│ • Write descriptions                    │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Step 4: Interactive Configuration       │
│ • Display proposed structure            │
│ • User reviews & refines                │
│ • Select/edit tools                     │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Step 5: Code Generation                 │
│ • Generate MCP server                   │
│ • Generate CLI-Anything config          │
│ • Generate tests & docs                 │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Step 6: Deployment                      │
│ • Download package                      │
│ • Register runtime adapter              │
│ • Provide next steps                    │
└─────────────────────────────────────────┘
```

---

## 3. Information Extraction

### 3.1 OpenAPI Parser

**File:** `skills/mcp_creator/parsers/openapi.py`

```python
"""
OpenAPI Parser — Extract structured API information from OpenAPI 3.x specs.
"""

from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class APIParameter(BaseModel):
    """API endpoint parameter."""
    name: str
    location: str  # path, query, header, body
    type: str
    description: str | None = None
    required: bool = False
    default: Any | None = None
    enum: list[str] | None = None


class APIEndpoint(BaseModel):
    """API endpoint (operation)."""
    operation_id: str | None = None
    method: str
    path: str
    summary: str | None = None
    description: str | None = None
    parameters: list[APIParameter] = Field(default_factory=list)
    request_body_schema: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)
    deprecated: bool = False


class ParsedOpenAPI(BaseModel):
    """Complete parsed OpenAPI specification."""
    info: APIInfo
    endpoints: list[APIEndpoint]
    security_schemes: dict[str, SecurityScheme] = Field(default_factory=dict)
    raw_spec: dict[str, Any]
    
    def get_endpoints_by_tag(self, tag: str) -> list[APIEndpoint]:
        """Filter endpoints by tag."""
        return [ep for ep in self.endpoints if tag in ep.tags]


class OpenAPIParser:
    """Parse OpenAPI 3.x specifications."""
    
    async def parse_from_url(self, url: str) -> ParsedOpenAPI:
        """Fetch and parse OpenAPI spec from URL."""
        response = await self._client.get(url, timeout=30.0)
        spec = response.json()
        return self._parse_spec(spec, base_url=self._extract_base_url(spec))
    
    def _parse_endpoint(
        self,
        method: str,
        path: str,
        operation: dict[str, Any],
    ) -> APIEndpoint:
        """Parse a single endpoint operation."""
        parameters = []
        
        for param in operation.get("parameters", []):
            param_schema = param.get("schema", {})
            parameters.append(APIParameter(
                name=param["name"],
                location=param["in"],
                type=param_schema.get("type", "string"),
                description=param.get("description"),
                required=param.get("required", False),
                default=param_schema.get("default"),
                enum=param_schema.get("enum"),
            ))
        
        return APIEndpoint(
            operation_id=operation.get("operationId"),
            method=method.upper(),
            path=path,
            summary=operation.get("summary"),
            description=operation.get("description"),
            parameters=parameters,
            request_body_schema=self._extract_request_body(operation),
            response_schema=self._extract_response(operation),
            tags=operation.get("tags", []),
            deprecated=operation.get("deprecated", False),
        )
```

### 3.2 GraphQL Parser

**File:** `skills/mcp_creator/parsers/graphql.py`

```python
"""
GraphQL Introspection Parser — Extract API info from GraphQL introspection queries.
"""

class GraphQLParser:
    """Parse GraphQL schemas via introspection."""
    
    INTROSPECTION_QUERY = """
    query IntrospectionQuery {
      __schema {
        queryType { name }
        mutationType { name }
        types {
          name
          kind
          description
          fields {
            name
            description
            args { ... }
            type { ... }
          }
        }
      }
    }
    """
    
    async def parse_from_url(self, url: str, headers: dict | None = None) -> ParsedGraphQL:
        """Introspect GraphQL endpoint and parse schema."""
        response = await self._client.post(
            url,
            json={"query": self.INTROSPECTION_QUERY},
            headers=headers,
            timeout=30.0,
        )
        data = response.json()
        return self._parse_schema(data["data"]["__schema"])
```

### 3.3 Unified Parser Interface

**File:** `skills/mcp_creator/parsers/__init__.py`

```python
"""
Unified API Parser — Detect and parse any API type (OpenAPI or GraphQL).
"""

class UnifiedAPIParser:
    """Automatically detect API type and parse accordingly."""
    
    async def parse(self, url: str, api_type: APIType | None = None):
        """Parse API from URL with auto-detection."""
        if api_type is None:
            api_type = await self._detect_api_type(url)
        
        if api_type == APIType.OPENAPI:
            return await self._openapi_parser.parse_from_url(url)
        elif api_type == APIType.GRAPHQL:
            return await self._graphql_parser.parse_from_url(url)
```

---

## 4. Semantic Enrichment

### 4.1 External Prompt Files

**Directory:** `skills/mcp_creator/prompts/`

```
prompts/
├── README.md
├── enrichment/
│   ├── openapi_enrichment.md       # OpenAPI analysis prompt
│   └── graphql_enrichment.md       # GraphQL analysis prompt
└── validation/
    └── security_review.md          # Security check prompt
```

### 4.2 Prompt Loader

**File:** `skills/mcp_creator/loaders/prompt_loader.py`

```python
"""
Prompt Loader — Load prompt templates from Markdown files at runtime.
"""

class PromptLoader:
    """Load and cache prompt templates from Markdown files."""
    
    def load(self, prompt_name: str, **variables: Any) -> str:
        """Load a prompt template and substitute variables."""
        prompt_path = self._prompts_dir / f"{prompt_name}.md"
        template = self._load_file(prompt_path)
        return self._substitute_variables(template, variables)
    
    def reload(self) -> None:
        """Clear cache to reload prompts from disk."""
        self._cache.clear()
```

### 4.3 OpenAPI Enrichment Prompt

**File:** `skills/mcp_creator/prompts/enrichment/openapi_enrichment.md`

```markdown
---
title: OpenAPI Semantic Enrichment
description: Analyze OpenAPI spec and suggest semantic improvements
version: 1.0
---

# OpenAPI Semantic Enrichment

You are an expert API designer. Analyze this OpenAPI specification and suggest 
improvements for MCP server generation.

## Input API Information

**API Title:** {api_title}  
**API Version:** {api_version}  
**Total Endpoints:** {endpoint_count}

### Endpoints:
```json
{endpoints_json}
```

## Your Task

1. **Semantic Tool Names**: Convert operationIds to meaningful action names
   - Bad: `get_users_id`, `repos_owner_repo_issues_get`
   - Good: `get_user_profile`, `list_repository_issues`

2. **Logical Groupings**: Group into 3-5 categories by business domain

3. **Enhanced Descriptions**: Clear descriptions for humans and AI agents

## Output Format

```json
{
  "suggested_server_name": "short-name",
  "categories": [
    {
      "name": "Category Name",
      "description": "What this category does",
      "tools": ["tool_name_1", "tool_name_2"]
    }
  ],
  "tools": {
    "tool_name": {
      "original_name": "original operationId",
      "suggested_name": "semantic_name",
      "description": "Clear description",
      "category": "Category Name",
      "parameters": [...],
      "examples": [...]
    }
  },
  "notes": ["Important considerations"]
}
```
```

### 4.4 Enrichment Engine

**File:** `skills/mcp_creator/enrichment/engine.py`

```python
"""
Semantic Enrichment Engine — Use LLM to enhance API structure.
"""

class EnrichmentEngine:
    """Enrich parsed API structure with semantic meaning."""
    
    def __init__(self):
        self._llm = get_llm("blitz/master")
        self._prompt_loader = PromptLoader()
    
    async def enrich_openapi(self, api_title: str, api_version: str, 
                            api_description: str | None, 
                            endpoints: list[dict]) -> EnrichedAPI:
        """Enrich OpenAPI endpoints."""
        prompt = self._prompt_loader.load(
            "enrichment/openapi_enrichment",
            api_title=api_title,
            api_version=api_version,
            api_description=api_description or "No description",
            endpoint_count=len(endpoints),
            endpoints_json=json.dumps(endpoints, indent=2)[:10000],
        )
        
        response = await self._llm.ainvoke(prompt)
        return self._parse_response(response.content)
```

---

## 5. Interactive UI Flow

### 5.1 User Journey

```
Step 1: Natural Language Input
User: "Create MCP server for GitHub API"

Step 2: API Detection
System: "Detected GitHub API v3.0 (OpenAPI)"
        "847 endpoints found"

Step 3: Authentication
System: "GitHub requires Bearer token"
User: [Enters token]

Step 4: Semantic Analysis (LLM)
System: Analyzing... ✓

Step 5: Interactive Configuration (UI)
┌─ Repository Management (12 tools) ─┐
│ ☑ list_repositories               │
│ ☑ create_repository               │
│ ☐ delete_repository  [excluded]   │
│ ☑ get_repository                  │
└────────────────────────────────────┘

Step 6: Code Generation
Generating: server.py, requirements.txt, tests...

Step 7: Output
📦 Download: github_mcp_server.zip
⚡ Runtime: Adapter "github" registered
```

### 5.2 UI State Management

**File:** `skills/mcp_creator/ui/state.py`

```python
class CreationStep(Enum):
    INPUT = auto()
    DETECTION = auto()
    AUTH = auto()
    PARSING = auto()
    ENRICHMENT = auto()
    CONFIGURATION = auto()
    GENERATION = auto()
    RESULTS = auto()


class UIState(BaseModel):
    """Current UI state."""
    step: CreationStep = CreationStep.INPUT
    api_url: str | None = None
    api_type: str | None = None
    raw_spec: dict | None = None
    parsed_api: Any | None = None
    enriched_api: Any | None = None
    selected_tools: set[str] = Field(default_factory=set)
    tool_overrides: dict[str, dict] = Field(default_factory=dict)
    server_name: str = "api-server"
```

---

## 6. Code Generation

### 6.1 Template Structure

```
templates/
├── mcp_server/
│   ├── main.py.jinja2
│   ├── requirements.txt.jinja2
│   └── README.md.jinja2
├── cli_anything/
│   └── config.yaml.jinja2
└── tests/
    └── test_server.py.jinja2
```

### 6.2 MCP Server Template

**File:** `templates/mcp_server/main.py.jinja2`

```jinja2
"""
{{ server_name }} MCP Server
Generated by AgentOS MCP Server Creator
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("{{ server_name }}")

{% for tool in tools %}
@mcp.tool()
async def {{ tool.suggested_name }}(
    {% for param in tool.parameters %}
    {{ param.name }}: {{ param.type_hint }}{% if not param.required %} = {{ param.default }}{% endif %},
    {% endfor %}
) -> dict[str, Any]:
    """
    {{ tool.description }}
    
    Args:
        {% for param in tool.parameters %}
        {{ param.name }}: {{ param.description }}
        {% endfor %}
    """
    # Implementation
    path = "{{ tool.path }}"
    {% for param in tool.parameters if param.location == "path" %}
    path = path.replace("{{ '{' + param.name + '}' }}", str({{ param.name }}))
    {% endfor %}
    
    result = await client.request("{{ tool.method }}", path, ...)
    return {"success": True, "result": result}

{% endfor %}

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 6.3 Code Generator

**File:** `skills/mcp_creator/generators/code_generator.py`

```python
class CodeGenerator:
    """Generate MCP server code using Jinja2 templates."""
    
    def generate_mcp_server(self, **context) -> dict[str, str]:
        """Generate complete MCP server package."""
        files = {}
        
        template = self._jinja.get_template("mcp_server/main.py.jinja2")
        files["server.py"] = template.render(**context)
        
        template = self._jinja.get_template("cli_anything/config.yaml.jinja2")
        files["cli-anything.yaml"] = template.render(**context)
        
        return files
    
    def create_zip_package(self, files: dict[str, str], server_name: str) -> BytesIO:
        """Create ZIP archive."""
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for filename, content in files.items():
                zf.writestr(f"{server_name}/{filename}", content)
        return zip_buffer
```

---

## 7. Integration with Universal Framework

### 7.1 Architecture Integration

The skill **builds on** Topic #21 (Universal Integration Framework):

```
MCP Creator Skill
       │
       ▼
IntegrationRegistry (Topic #21)
       │
       ▼
SecureAdapterWrapper
       │
       ▼
   Adapters (MCP, CLI-Anything)
```

### 7.2 Adapter Registration

**File:** `skills/mcp_creator/deployment/adapter_registration.py`

```python
class AdapterRegistrar:
    """Register generated adapters with IntegrationRegistry."""
    
    async def register_mcp_adapter(
        self,
        server_name: str,
        server_url: str,
        auth_token: str | None,
    ) -> dict[str, Any]:
        """Register generated MCP server as runtime adapter."""
        config = AdapterConfig(
            name=server_name,
            adapter_type="mcp",
            config={
                "url": f"{server_url}/sse",
                "auth_token": auth_token,
            },
            required_permissions=[f"{server_name}:execute"],
        )
        
        adapter = await self._registry.register_adapter(config)
        tools = await adapter.discover_tools()
        
        return {
            "adapter_name": server_name,
            "tools_registered": len(tools),
            "status": "active",
        }
```

### 7.3 Deployment Modes

```python
class DeploymentMode(Enum):
    LOCAL_RUNTIME = auto()      # Run in AgentOS process
    DOCKER_CONTAINER = auto()   # Run as Docker container  
    EXTERNAL_HOSTING = auto()   # User hosts externally
```

---

## 8. Example Scenarios

### Scenario 1: GitHub API (Complex)

```
Input: "Create MCP server for GitHub API"
Parsed: 847 endpoints
Selected: 24 tools (3 categories)
Output: github_mcp_server.zip + Runtime adapter
Time: ~2 minutes
```

### Scenario 2: Simple Internal API

```
Input: "Create MCP for employee API"
Parsed: 4 endpoints
Selected: All 4 (auto-selected for small APIs)
Output: employee_mcp_server.zip
Time: ~30 seconds
```

### Scenario 3: Stripe (Financial)

```
Input: "Create MCP for Stripe payments"
Features: 
- Security warnings in generated code
- Idempotency key handling
- PCI compliance notes
Selected: 18 payment tools
```

---

## 9. Implementation Phases

### Phase 1: Parser Infrastructure (2 weeks)
- [ ] OpenAPI 3.x parser
- [ ] GraphQL introspection parser
- [ ] API type auto-detection
- [ ] Unified parser interface

### Phase 2: Prompt System (1 week)
- [ ] External prompt file structure
- [ ] Prompt loader with caching
- [ ] Hot-reload capability
- [ ] OpenAPI enrichment prompt
- [ ] GraphQL enrichment prompt

### Phase 3: Enrichment Engine (1 week)
- [ ] LLM integration
- [ ] Response parsing
- [ ] EnrichedAPI models
- [ ] Error handling

### Phase 4: UI & State Management (2 weeks)
- [ ] UI state models
- [ ] Screen components
- [ ] Interactive configurator
- [ ] Tool editor modal

### Phase 5: Code Generation (2 weeks)
- [ ] Jinja2 template engine
- [ ] MCP server templates
- [ ] CLI-Anything templates
- [ ] Test generation
- [ ] ZIP packaging

### Phase 6: Deployment & Integration (1 week)
- [ ] Adapter registration
- [ ] Three deployment modes
- [ ] Runtime integration
- [ ] Database persistence

### Phase 7: Testing & Polish (1 week)
- [ ] Unit tests
- [ ] Integration tests
- [ ] Example APIs
- [ ] Documentation

**Total: 10 weeks**

---

## 10. Database Schema

```sql
-- MCP Server Creation tracking
CREATE TABLE mcp_server_creations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    -- Input
    api_url TEXT NOT NULL,
    api_type VARCHAR(20),  -- openapi, graphql
    
    -- Intermediate state
    parsed_spec JSONB DEFAULT '{}',
    enriched_spec JSONB DEFAULT '{}',
    user_configuration JSONB DEFAULT '{}',
    
    -- Output
    server_name VARCHAR(64),
    generated_files JSONB DEFAULT '{}',
    
    -- Status
    status VARCHAR(20) DEFAULT 'started',
    error_message TEXT,
    
    -- Deployment
    deployment_mode VARCHAR(20),
    adapter_registered BOOLEAN DEFAULT FALSE,
    adapter_name VARCHAR(64),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_mcp_creations_user ON mcp_server_creations(user_id);
CREATE INDEX idx_mcp_creations_status ON mcp_server_creations(status);
```

---

## 11. File Structure

```
skills/mcp_creator/
├── __init__.py
├── README.md
├── skill.py                    # Main skill orchestrator
│
├── parsers/                    # API parsing
│   ├── __init__.py
│   ├── openapi.py
│   ├── graphql.py
│   └── base.py
│
├── prompts/                    # LLM prompts (external)
│   ├── README.md
│   ├── enrichment/
│   │   ├── openapi_enrichment.md
│   │   └── graphql_enrichment.md
│   └── validation/
│       └── security_review.md
│
├── loaders/                    # Prompt loading
│   ├── __init__.py
│   └── prompt_loader.py
│
├── enrichment/                 # Semantic enrichment
│   ├── __init__.py
│   ├── engine.py
│   └── models.py
│
├── ui/                         # UI components
│   ├── __init__.py
│   ├── state.py
│   └── components.py
│
├── generators/                 # Code generation
│   ├── __init__.py
│   └── code_generator.py
│
├── templates/                  # Jinja2 templates
│   ├── mcp_server/
│   │   ├── main.py.jinja2
│   │   ├── requirements.txt.jinja2
│   │   └── README.md.jinja2
│   ├── cli_anything/
│   │   └── config.yaml.jinja2
│   └── tests/
│       └── test_server.py.jinja2
│
├── deployment/                 # Adapter registration
│   ├── __init__.py
│   └── adapter_registration.py
│
└── models/                     # Database models
    ├── __init__.py
    └── db_models.py
```

---

## 12. Open Questions

1. **Rate Limiting**: Should we add rate limiting for LLM calls during enrichment?
2. **Caching**: Cache parsed specs to avoid re-fetching?
3. **Versioning**: Version generated code for backward compatibility?
4. **Custom Templates**: Allow users to provide custom Jinja2 templates?
5. **Multi-language**: Support TypeScript/JavaScript MCP servers in addition to Python?

---

*Design complete. Ready for implementation planning.*
