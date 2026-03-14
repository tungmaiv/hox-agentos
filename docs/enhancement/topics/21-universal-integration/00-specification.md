# Universal Integration Framework - Design Specification

**Topic:** #21 - Universal Integration
**Status:** 🟡 PENDING → ✅ DESIGNED
**Target Version:** v1.7+
**Date:** 2026-03-17
**Priority:** Medium

---

## Executive Summary

The Universal Integration Framework provides a modular, extensible architecture for connecting AgentOS to external systems through a unified adapter pattern. This framework resolves the deferred MCP vs CLI-Anything discussion by supporting both approaches through a consistent adapter protocol, while also enabling REST API, webhook, and future integration types.

**Key Features:**
- **Adapter Protocol** — Abstract base class for all integration types (MCP, REST, Webhook, CLI-Anything)
- **Unified Security** — All adapters go through identical 3-gate security (RBAC + ACL + audit logging)
- **CLI-Anything Support** — Subprocess wrapper with line-by-line streaming and filesystem path validation
- **Webhook Integration** — Bidirectional event handling with HMAC-SHA256 signature verification
- **Plugin SDK** — Third parties can create custom adapters via Python entry points
- **Modular Design** — Integration layer is separate from core AgentOS for independent maintenance
- **Migration Path** — Smooth transition from existing MCP/OpenAPI bridge code

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Architecture Overview](#2-architecture-overview)
3. [Adapter Protocol Design](#3-adapter-protocol-design)
4. [Unified Security Wrapper](#4-unified-security-wrapper)
5. [Individual Adapter Designs](#5-individual-adapter-designs)
6. [Plugin SDK](#6-plugin-sdk)
7. [Configuration and Registry](#7-configuration-and-registry)
8. [Database Schema](#8-database-schema)
9. [Migration from Existing Code](#9-migration-from-existing-code)
10. [Implementation Phases](#10-implementation-phases)
11. [Testing Strategy](#11-testing-strategy)
12. [Open Questions & Future Work](#12-open-questions--future-work)

---

## 1. Requirements

### 1.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1 | Support MCP servers via HTTP+SSE | High |
| FR2 | Support REST API integrations | High |
| FR3 | Support webhook receivers (bidirectional) | High |
| FR4 | Support CLI-Anything generated CLIs | High |
| FR5 | Unified 3-gate security across all adapters | High |
| FR6 | Plugin SDK for third-party adapters | Medium |
| FR7 | Adapter lifecycle management (init, health, shutdown) | High |
| FR8 | Tool discovery and registration | High |
| FR9 | Streaming support where applicable | Medium |
| FR10 | Configuration validation and persistence | Medium |

### 1.2 Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR1 | Modular design separate from core AgentOS | High |
| NFR2 | Backward compatibility with existing MCP integration | High |
| NFR3 | Consistent error handling across adapters | Medium |
| NFR4 | Audit logging for all tool calls | High |
| NFR5 | Health monitoring for all adapters | Medium |
| NFR6 | Graceful degradation on adapter failure | Medium |

### 1.3 Security Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| SR1 | Gate 2 (RBAC) applied uniformly | High |
| SR2 | Gate 3 (ACL) applied uniformly | High |
| SR3 | CLI-Anything path validation | High |
| SR4 | Webhook signature verification (HMAC-SHA256) | High |
| SR5 | Audit logging with user, tool, duration | High |
| SR6 | No credential exposure in logs | High |

---

## 2. Architecture Overview

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AGENTOS CORE                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Agents    │  │   Memory    │  │   Scheduler │  │   Tool Registry     │  │
│  │  (LangGraph)│  │  (pgvector) │  │   (Celery)  │  │  (registry_entries) │  │
│  └──────┬──────┘  └─────────────┘  └─────────────┘  └──────────┬──────────┘  │
│         │                                                       │             │
│         │         ┌─────────────────────────────────────────────┘             │
│         │         │                                                           │
│         └─────────►         UNIVERSAL INTEGRATION LAYER                       │
│                   │         (Separate from Core)                              │
│                   │                                                           │
│                   │  ┌─────────────────────────────────────────────────────┐  │
│                   │  │         IntegrationRegistry                          │  │
│                   │  │  - Adapter lifecycle management                      │  │
│                   │  │  - Tool discovery aggregation                        │  │
│                   │  │  - Tool routing                                      │  │
│                   │  └──────────────────┬──────────────────────────────────┘  │
│                   │                     │                                     │
│                   │  ┌──────────────────┴──────────────────────────────────┐  │
│                   │  │              SecureAdapterWrapper                    │  │
│                   │  │         (Unified 3-Gate Security)                    │  │
│                   │  │  • Gate 2: RBAC permission check                     │  │
│                   │  │  • Gate 3: Tool ACL check                            │  │
│                   │  │  • Audit logging                                     │  │
│                   │  │  • CLI-Anything path validation                      │  │
│                   │  └──────────────────┬──────────────────────────────────┘  │
│                   │                     │                                     │
│                   │         ┌───────────┼───────────┐                         │
│                   │         ▼           ▼           ▼                         │
│                   │  ┌──────────┐ ┌──────────┐ ┌──────────┐                  │
│                   │  │   MCP    │ │   REST   │ │ Webhook  │                  │
│                   │  │  Adapter │ │  Adapter │ │  Adapter │                  │
│                   │  └────┬─────┘ └────┬─────┘ └────┬─────┘                  │
│                   │       │            │            │                        │
│                   │       ▼            ▼            ▼                        │
│                   │  MCP Servers   HTTP APIs   External Events               │
│                   │  (HTTP+SSE)   (REST/CRUD)  (GitHub/Slack)                │
│                   │                                                          │
│                   │         ┌───────────┬───────────┐                        │
│                   │         ▼           ▼           ▼                        │
│                   │  ┌──────────┐ ┌──────────┐ ┌──────────┐                 │
│                   │  │   CLI    │ │ OpenAPI  │ │  Custom  │                  │
│                   │  │Anything  │ │  Adapter │ │ Adapters │                  │
│                   │  │  Adapter │ │          │ │ (Plugin) │                  │
│                   │  └────┬─────┘ └────┬─────┘ └────┬─────┘                  │
│                   │       │            │            │                        │
│                   │       ▼            ▼            ▼                        │
│                   │  LibreOffice  Auto-discovered   3rd Party                │
│                   │  GIMP/Blender  from spec        Extensions               │
│                   │                                                          │
│                   └─────────────────────────────────────────────────────────┘
│
│                   ┌─────────────────────────────────────────────────────────┐
│                   │              Plugin SDK (3rd Party)                      │
│                   │         • BaseAdapter / BaseHTTPAdapter                  │
│                   │         • Testing utilities                              │
│                   │         • Cookiecutter templates                         │
│                   └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Adapter Comparison Matrix

| Adapter | Protocol | Streaming | Bidirectional | Discovery | Primary Use Case |
|---------|----------|-----------|---------------|-----------|------------------|
| **MCP** | HTTP+SSE JSON-RPC | ✅ Native | ❌ | ✅ tools/list | Custom AgentOS-native tools |
| **REST** | HTTP/1.1 | ❌ | ❌ | Manual config | Generic REST APIs |
| **OpenAPI** | HTTP/1.1 | ❌ | ❌ | ✅ Spec parsing | Documented REST APIs |
| **Webhook** | HTTP POST | ❌ | ✅ | ✅ Event types | External system events |
| **CLI-Anything** | Subprocess | ✅ Line-by-line | ❌ | ✅ --list-commands | Existing software |
| **Custom (SDK)** | Varies | Configurable | Configurable | Configurable | Third-party integrations |

### 2.3 Key Architectural Principles

| Principle | Implementation |
|-----------|----------------|
| **Separation** | Integration layer is separate module from core AgentOS |
| **Modularity** | Each adapter is independent, swappable |
| **Extensibility** | Plugin SDK allows third-party adapters |
| **Security** | Unified 3-gate security across ALL adapters |
| **Consistency** | All adapters implement same protocol |

---

## 3. Adapter Protocol Design

### 3.1 Core Protocol Interface

**File:** `integrations/core/adapter.py`

```python
"""
Integration Adapter Protocol — Abstract base class for all integration types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Literal, Protocol

from pydantic import BaseModel, Field


class AdapterCapabilities(BaseModel):
    """Capabilities advertised by an adapter."""
    
    streaming: bool = False
    discovery: bool = True
    bidirectional: bool = False
    health_check: bool = True
    batch_operations: bool = False


class ToolDefinition(BaseModel):
    """Standardized tool definition across all adapters."""
    
    name: str
    display_name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    required_permissions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Standardized tool execution result."""
    
    success: bool
    result: Any | None = None
    error: str | None = None
    duration_ms: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckResult(BaseModel):
    """Health check result."""
    
    status: HealthStatus
    message: str | None = None
    last_check: datetime
    latency_ms: int
    details: dict[str, Any] = Field(default_factory=dict)


class StreamChunk(BaseModel):
    """Single chunk of a streaming response."""
    
    chunk_type: Literal["content", "error", "done"] = "content"
    content: str | dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntegrationAdapter(ABC):
    """
    Abstract base class for all integration adapters.
    
    Adapters bridge AgentOS to external systems (MCP servers, REST APIs,
    webhooks, CLI tools, etc.).
    """
    
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self._capabilities: AdapterCapabilities | None = None
        self._last_health_check: HealthCheckResult | None = None
    
    @property
    @abstractmethod
    def adapter_type(self) -> str:
        """Return the adapter type identifier."""
        raise NotImplementedError
    
    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Return adapter capabilities."""
        raise NotImplementedError
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the adapter."""
        raise NotImplementedError
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shutdown the adapter."""
        raise NotImplementedError
    
    @abstractmethod
    async def discover_tools(self) -> list[ToolDefinition]:
        """Discover and return available tools."""
        raise NotImplementedError
    
    @abstractmethod
    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> ToolResult:
        """Execute a tool with the given arguments."""
        raise NotImplementedError
    
    async def execute_tool_stream(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> AsyncIterator[StreamChunk]:
        """Execute a tool with streaming response."""
        raise NotImplementedError(
            f"Adapter '{self.name}' does not support streaming"
        )
    
    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """Check adapter health."""
        raise NotImplementedError
    
    async def register_trigger(
        self,
        trigger_name: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Register a bidirectional trigger."""
        raise NotImplementedError(
            f"Adapter '{self.name}' does not support bidirectional triggers"
        )
    
    async def unregister_trigger(self, trigger_id: str) -> None:
        """Unregister a trigger."""
        raise NotImplementedError
    
    async def handle_inbound_event(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> ToolResult:
        """Handle an inbound event."""
        raise NotImplementedError(
            f"Adapter '{self.name}' does not support inbound events"
        )


class AdapterInitError(Exception):
    """Raised when adapter initialization fails."""
    pass


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    pass
```

### 3.2 Protocol Design Decisions

| Decision | Rationale |
|----------|-----------|
| Abstract Base Class | Enforces contract at runtime, clear method signatures |
| Pydantic Models | Validation, serialization, type safety |
| Async throughout | Consistent with FastAPI/asyncpg architecture |
| Optional streaming | Not all adapters support it, default raises error |
| Optional bidirectional | Only webhooks need inbound handling |
| Context dict | Flexible execution context without tight coupling |

---

## 4. Unified Security Wrapper

### 4.1 Security Wrapper Implementation

**File:** `integrations/core/security.py`

```python
"""
Unified Security Wrapper — Applies AgentOS 3-gate security to all integrations.
"""

import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

import structlog
from fastapi import HTTPException

from core.logging import get_audit_logger
from core.models.user import UserContext
from security.acl import check_tool_acl
from security.rbac import has_permission

from .adapter import (
    AdapterCapabilities,
    IntegrationAdapter,
    StreamChunk,
    ToolDefinition,
    ToolResult,
)

logger = structlog.get_logger(__name__)
audit_logger = get_audit_logger()


@dataclass(frozen=True)
class SecurityContext:
    """Security context passed through tool execution."""
    user: UserContext
    tool_fqn: str
    tool_def: ToolDefinition
    conversation_id: str | None = None
    trace_id: str | None = None
    client_ip: str | None = None


class SecureAdapterWrapper:
    """
    Wrapper that applies AgentOS security gates to any IntegrationAdapter.
    
    Ensures ALL adapters — MCP, REST, Webhook, CLI-Anything —
    go through identical security checks and audit logging.
    """
    
    def __init__(self, adapter: IntegrationAdapter) -> None:
        self._adapter = adapter
        self._capabilities = adapter.capabilities
        
        logger.info(
            "secure_adapter_wrapped",
            adapter_name=adapter.name,
            adapter_type=adapter.adapter_type,
            capabilities=adapter.capabilities.model_dump(),
        )
    
    @property
    def name(self) -> str:
        return self._adapter.name
    
    @property
    def adapter_type(self) -> str:
        return self._adapter.adapter_type
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return self._capabilities
    
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        security_context: SecurityContext,
    ) -> ToolResult:
        """Execute tool with full security gates applied."""
        start_ms = int(time.monotonic() * 1000)
        
        # Gate 2: RBAC
        for permission in security_context.tool_def.required_permissions:
            has_perm = await has_permission(
                security_context.user,
                permission,
                None,
            )
            if not has_perm:
                elapsed = int(time.monotonic() * 1000) - start_ms
                audit_logger.info(
                    "tool_call_denied",
                    tool=security_context.tool_fqn,
                    user_id=str(security_context.user["user_id"]),
                    allowed=False,
                    duration_ms=elapsed,
                    gate="rbac",
                    missing_permission=permission,
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permission: {permission}",
                )
        
        # Gate 3: ACL
        if self._adapter.adapter_type == "cli_anything":
            await self._check_cli_acl(
                security_context.user["user_id"],
                arguments,
            )
        
        allowed = await check_tool_acl(
            security_context.user["user_id"],
            security_context.tool_fqn,
            None,
        )
        
        elapsed = int(time.monotonic() * 1000) - start_ms
        audit_logger.info(
            "tool_call",
            tool=security_context.tool_fqn,
            user_id=str(security_context.user["user_id"]),
            adapter_type=self._adapter.adapter_type,
            allowed=allowed,
            duration_ms=elapsed,
            gate="acl",
        )
        
        if not allowed:
            raise HTTPException(status_code=403, detail="Tool call denied by ACL")
        
        # Execute via adapter
        execution_context = {
            "user_id": str(security_context.user["user_id"]),
            "conversation_id": security_context.conversation_id,
            "trace_id": security_context.trace_id,
            "tool_fqn": security_context.tool_fqn,
            "start_time_ms": start_ms,
        }
        
        try:
            adapter_name, local_tool_name = self._parse_tool_fqn(
                security_context.tool_fqn
            )
            
            result = await self._adapter.execute_tool(
                local_tool_name,
                arguments,
                execution_context,
            )
            
            result.metadata.update({
                "security_checked": True,
                "gates_passed": ["rbac", "acl"],
                "user_id": str(security_context.user["user_id"]),
            })
            
            return result
            
        except Exception as exc:
            logger.error(
                "adapter_execution_failed",
                adapter=self._adapter.name,
                tool=local_tool_name,
                error=str(exc),
            )
            raise
    
    def _parse_tool_fqn(self, tool_fqn: str) -> tuple[str, str]:
        """Parse 'adapter_name.tool_name' into components."""
        parts = tool_fqn.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid tool FQN: {tool_fqn}")
        return parts[0], parts[1]
    
    async def _check_cli_acl(
        self,
        user_id: str,
        arguments: dict[str, Any],
    ) -> None:
        """Additional ACL check for CLI-Anything adapters."""
        file_paths = self._extract_file_paths(arguments)
        
        for path in file_paths:
            if not self._is_path_allowed(path, user_id):
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied to path: {path}",
                )
    
    def _extract_file_paths(self, arguments: dict[str, Any]) -> list[str]:
        """Extract file paths from tool arguments."""
        paths = []
        
        def search_dict(d: dict[str, Any]) -> None:
            for key, value in d.items():
                if isinstance(value, str) and (
                    key.endswith("_path") 
                    or key.endswith("_file") 
                    or "/" in value 
                    or "\\" in value
                ):
                    paths.append(value)
                elif isinstance(value, dict):
                    search_dict(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and ("/" in item or "\\" in item):
                            paths.append(item)
                        elif isinstance(item, dict):
                            search_dict(item)
        
        search_dict(arguments)
        return paths
    
    def _is_path_allowed(self, path: str, user_id: str) -> bool:
        """Check if a file path is allowed for the user."""
        import os
        
        path = os.path.abspath(os.path.expanduser(path))
        
        allowed_bases = [
            f"/storage/users/{user_id}",
            "/tmp",
            "/var/tmp",
        ]
        
        whitelist = self._adapter.config.get("path_whitelist", [])
        allowed_bases.extend(whitelist)
        
        return any(
            path.startswith(os.path.abspath(base))
            for base in allowed_bases
        )
    
    # Passthrough methods
    async def discover_tools(self) -> list[ToolDefinition]:
        return await self._adapter.discover_tools()
    
    async def health_check(self):
        return await self._adapter.health_check()
    
    async def initialize(self):
        return await self._adapter.initialize()
    
    async def shutdown(self):
        return await self._adapter.shutdown()
```

### 4.2 Security Flow

```
User calls tool → Tool Registry → IntegrationRegistry → SecureAdapterWrapper
                                                        │
                    ┌───────────────────────────────────┼───────────────────────────────────┐
                    ▼                                   ▼                                   ▼
            ┌──────────────┐                  ┌──────────────┐                      ┌──────────────┐
            │   Gate 2     │                  │   Gate 3     │                      │   Audit      │
            │  RBAC Check  │ ───────────────► │  ACL Check   │ ───────────────────► │    Log       │
            └──────────────┘                  └──────────────┘                      └──────────────┘
                   │                                 │                                     │
              Forbidden?                        Forbidden?                            Always
                   │                                 │                                     │
                   ▼                                 ▼                                     ▼
            Return 403                         Return 403                           Continue
                                                                                        │
                                                                                        ▼
                                                                              Adapter.execute_tool()
```

---

## 5. Individual Adapter Designs

### 5.1 MCP Adapter (Refactored)

**File:** `integrations/adapters/mcp/adapter.py`

```python
"""MCP Adapter — HTTP+SSE Model Context Protocol integration."""

from typing import Any, AsyncIterator

import httpx
import structlog

from core.logging import timed
from integrations.core.adapter import (
    AdapterCapabilities,
    AdapterInitError,
    HealthCheckResult,
    HealthStatus,
    IntegrationAdapter,
    StreamChunk,
    ToolDefinition,
    ToolResult,
)

logger = structlog.get_logger(__name__)


class MCPAdapter(IntegrationAdapter):
    """HTTP+SSE MCP adapter using JSON-RPC protocol."""
    
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        self._base_url: str = ""
        self._headers: dict[str, str] = {}
        self._timeout: float = 30.0
        self._client: httpx.AsyncClient | None = None
    
    @property
    def adapter_type(self) -> str:
        return "mcp"
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            discovery=True,
            bidirectional=False,
            health_check=True,
            batch_operations=False,
        )
    
    async def initialize(self) -> None:
        url = self.config.get("url")
        if not url:
            raise AdapterInitError("MCP adapter requires 'url' in config")
        
        self._base_url = url.rstrip("/")
        self._timeout = float(self.config.get("timeout_seconds", 30.0))
        
        auth_token = self.config.get("auth_token")
        if auth_token:
            self._headers["Authorization"] = f"Bearer {auth_token}"
        
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers=self._headers,
        )
    
    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def discover_tools(self) -> list[ToolDefinition]:
        if not self._client:
            raise AdapterInitError("Adapter not initialized")
        
        try:
            response = await self._client.post(
                f"{self._base_url}/sse",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            )
            response.raise_for_status()
            data = response.json()
            
            tools = data.get("result", {}).get("tools", [])
            
            return [
                ToolDefinition(
                    name=f"{self.name}.{tool['name']}",
                    display_name=tool.get("name", "unknown"),
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {"type": "object"}),
                    required_permissions=[f"{self.name}:execute"],
                    metadata={
                        "mcp_server": self.name,
                        "mcp_tool_name": tool["name"],
                    },
                )
                for tool in tools
            ]
        except Exception as exc:
            logger.error("mcp_discovery_failed", adapter=self.name, error=str(exc))
            return []
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> ToolResult:
        if not self._client:
            raise AdapterInitError("Adapter not initialized")
        
        start_ms = context.get("start_time_ms", 0)
        
        with timed(logger, "mcp_tool_call", tool=tool_name, adapter=self.name):
            try:
                response = await self._client.post(
                    f"{self._base_url}/sse",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": arguments},
                        "id": 2,
                    },
                )
                response.raise_for_status()
                result = response.json()
                
                if "error" in result:
                    return ToolResult(
                        success=False,
                        error=result["error"].get("message", "Unknown error"),
                        duration_ms=int(time.monotonic() * 1000) - start_ms,
                    )
                
                return ToolResult(
                    success=True,
                    result=result.get("result"),
                    duration_ms=int(time.monotonic() * 1000) - start_ms,
                )
            except Exception as exc:
                return ToolResult(
                    success=False,
                    error=str(exc),
                    duration_ms=int(time.monotonic() * 1000) - start_ms,
                )
    
    async def health_check(self) -> HealthCheckResult:
        import time
        from datetime import datetime, timezone
        
        start = time.monotonic()
        
        try:
            if not self._client:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Adapter not initialized",
                    last_check=datetime.now(timezone.utc),
                    latency_ms=0,
                )
            
            response = await self._client.post(
                f"{self._base_url}/sse",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 0},
                timeout=5.0,
            )
            
            latency_ms = int((time.monotonic() - start) * 1000)
            
            if response.status_code == 200:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    last_check=datetime.now(timezone.utc),
                    latency_ms=latency_ms,
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"HTTP {response.status_code}",
                    last_check=datetime.now(timezone.utc),
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(exc),
                last_check=datetime.now(timezone.utc),
                latency_ms=int((time.monotonic() - start) * 1000),
            )
```

### 5.2 REST API Adapter

**File:** `integrations/adapters/rest/adapter.py`

```python
"""REST API Adapter — Generic HTTP REST integration."""

from typing import Any, Literal

import httpx
import structlog

from integrations.core.adapter import (
    AdapterCapabilities,
    AdapterInitError,
    HealthCheckResult,
    IntegrationAdapter,
    ToolDefinition,
    ToolResult,
)

logger = structlog.get_logger(__name__)

AuthType = Literal["none", "bearer", "api_key", "basic", "oauth2"]


class RESTAdapter(IntegrationAdapter):
    """
    Generic REST API adapter.
    
    Configuration:
    {
        "base_url": "https://api.example.com",
        "auth_type": "bearer",
        "auth_config": {"token": "secret"},
        "endpoints": [...]
    }
    """
    
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        self._base_url: str = ""
        self._client: httpx.AsyncClient | None = None
        self._endpoints: dict[str, dict] = {}
    
    @property
    def adapter_type(self) -> str:
        return "rest"
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=False,
            discovery=True,
            bidirectional=False,
            health_check=True,
            batch_operations=False,
        )
    
    async def initialize(self) -> None:
        self._base_url = self.config.get("base_url", "").rstrip("/")
        if not self._base_url:
            raise AdapterInitError("REST adapter requires 'base_url'")
        
        headers = {"Accept": "application/json"}
        auth_config = self.config.get("auth_config", {})
        
        auth_type = self.config.get("auth_type", "none")
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
        elif auth_type == "api_key":
            header_name = auth_config.get("header", "X-API-Key")
            headers[header_name] = auth_config.get("key", "")
        
        self._client = httpx.AsyncClient(headers=headers)
        self._endpoints = {
            ep["name"]: ep 
            for ep in self.config.get("endpoints", [])
        }
    
    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def discover_tools(self) -> list[ToolDefinition]:
        tools = []
        
        for ep_name, ep_config in self._endpoints.items():
            properties = {}
            required = []
            
            for param in ep_config.get("parameters", []):
                properties[param["name"]] = {
                    "type": param.get("type", "string"),
                    "description": param.get("description", ""),
                }
                if param.get("required"):
                    required.append(param["name"])
            
            tools.append(ToolDefinition(
                name=f"{self.name}.{ep_name}",
                display_name=ep_config.get("display_name", ep_name),
                description=ep_config.get("description", ""),
                input_schema={
                    "type": "object",
                    "properties": properties,
                    "required": required if required else None,
                },
                required_permissions=[f"{self.name}:execute"],
                metadata={
                    "method": ep_config["method"],
                    "path": ep_config["path"],
                },
            ))
        
        return tools
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> ToolResult:
        if not self._client:
            raise AdapterInitError("Adapter not initialized")
        
        endpoint = self._endpoints.get(tool_name)
        if not endpoint:
            return ToolResult(
                success=False,
                error=f"Unknown endpoint: {tool_name}",
                duration_ms=0,
            )
        
        start_ms = context.get("start_time_ms", 0)
        
        try:
            path = endpoint["path"]
            for key, value in arguments.items():
                placeholder = f"{{{key}}}"
                if placeholder in path:
                    path = path.replace(placeholder, str(value))
            
            url = f"{self._base_url}{path}"
            method = endpoint["method"].upper()
            
            response = await self._client.request(
                method=method,
                url=url,
                params={k: v for k, v in arguments.items() if k in endpoint.get("query_params", [])},
                json={k: v for k, v in arguments.items() if k in endpoint.get("body_params", [])} or None,
            )
            response.raise_for_status()
            
            return ToolResult(
                success=True,
                result=response.json() if response.content else None,
                duration_ms=int(time.monotonic() * 1000) - start_ms,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                duration_ms=int(time.monotonic() * 1000) - start_ms,
            )
```

### 5.3 Webhook Adapter

**File:** `integrations/adapters/webhook/adapter.py`

```python
"""Webhook Adapter — Bidirectional webhook integration."""

import hmac
import hashlib
from datetime import datetime, timezone
from typing import Any

import structlog

from integrations.core.adapter import (
    AdapterCapabilities,
    AdapterInitError,
    HealthCheckResult,
    IntegrationAdapter,
    ToolDefinition,
    ToolResult,
)

logger = structlog.get_logger(__name__)


class WebhookAdapter(IntegrationAdapter):
    """
    Webhook receiver adapter.
    
    Configuration:
    {
        "webhook_base_url": "https://agentos.example.com/webhooks",
        "secret_header": "X-Webhook-Secret",
        "secret": "signing-secret",
        "events": [...]
    }
    """
    
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        self._webhook_url: str = ""
        self._registered_triggers: dict[str, dict] = {}
    
    @property
    def adapter_type(self) -> str:
        return "webhook"
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=False,
            discovery=True,
            bidirectional=True,
            health_check=True,
            batch_operations=False,
        )
    
    async def initialize(self) -> None:
        base_url = self.config.get("webhook_base_url")
        if not base_url:
            raise AdapterInitError("Webhook adapter requires 'webhook_base_url'")
        
        self._webhook_url = f"{base_url.rstrip('/')}/{self.name}"
    
    async def shutdown(self) -> None:
        for trigger_id in list(self._registered_triggers.keys()):
            await self.unregister_trigger(trigger_id)
    
    async def discover_tools(self) -> list[ToolDefinition]:
        events = self.config.get("events", [])
        
        return [
            ToolDefinition(
                name=f"{self.name}.{event['name']}",
                display_name=event.get("display_name", event['name']),
                description=event.get("description", ""),
                input_schema={
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string"},
                        "workflow_id": {"type": "string"},
                    },
                },
                required_permissions=[f"{self.name}:subscribe"],
                metadata={
                    "event_type": event["name"],
                    "payload_schema": event.get("payload_schema", {}),
                },
            )
            for event in events
        ]
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> ToolResult:
        trigger_config = await self.register_trigger(tool_name, arguments)
        
        return ToolResult(
            success=True,
            result={
                "status": "subscribed",
                "trigger_id": trigger_config["trigger_id"],
                "webhook_url": self._webhook_url,
            },
            duration_ms=0,
        )
    
    async def register_trigger(
        self,
        trigger_name: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        import uuid
        
        trigger_id = str(uuid.uuid4())
        
        trigger_config = {
            "trigger_id": trigger_id,
            "event_type": trigger_name,
            "filter": config.get("filter"),
            "workflow_id": config.get("workflow_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self._registered_triggers[trigger_id] = trigger_config
        
        return {
            "trigger_id": trigger_id,
            "webhook_url": f"{self._webhook_url}/{trigger_id}",
            "event_type": trigger_name,
        }
    
    async def unregister_trigger(self, trigger_id: str) -> None:
        if trigger_id in self._registered_triggers:
            del self._registered_triggers[trigger_id]
    
    async def handle_inbound_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ToolResult:
        secret = self.config.get("secret")
        secret_header = self.config.get("secret_header", "X-Webhook-Secret")
        
        if secret and headers:
            received_sig = headers.get(secret_header, "")
            expected_sig = hmac.new(
                secret.encode(),
                str(payload).encode(),
                hashlib.sha256,
            ).hexdigest()
            
            if not hmac.compare_digest(received_sig, expected_sig):
                return ToolResult(
                    success=False,
                    error="Invalid webhook signature",
                    duration_ms=0,
                )
        
        matching_triggers = []
        for trigger_id, trigger in self._registered_triggers.items():
            if trigger["event_type"] == event_type:
                matching_triggers.append(trigger)
        
        for trigger in matching_triggers:
            logger.info(
                "webhook_event_triggered",
                adapter=self.name,
                trigger_id=trigger["trigger_id"],
                workflow_id=trigger.get("workflow_id"),
            )
        
        return ToolResult(
            success=True,
            result={
                "triggers_matched": len(matching_triggers),
                "event_type": event_type,
            },
            duration_ms=0,
        )
```

### 5.4 CLI-Anything Adapter

**File:** `integrations/adapters/cli_anything/adapter.py`

```python
"""CLI-Anything Adapter — Wraps CLI-Anything generated CLIs."""

import asyncio
import json
import shutil
import subprocess
from typing import Any, AsyncIterator

import structlog

from integrations.core.adapter import (
    AdapterCapabilities,
    AdapterInitError,
    HealthCheckResult,
    HealthStatus,
    IntegrationAdapter,
    StreamChunk,
    ToolDefinition,
    ToolResult,
)

logger = structlog.get_logger(__name__)


class CLIAnythingAdapter(IntegrationAdapter):
    """
    CLI-Anything wrapper adapter.
    
    Configuration:
    {
        "cli_name": "cli-anything-libreoffice",
        "cli_path": "/usr/local/bin/cli-anything-libreoffice",
        "timeout_seconds": 120,
        "max_output_size": 10485760,
        "allowed_paths": ["/tmp", "/storage"],
        "stream_line_prefix": "STREAM:"
    }
    """
    
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        self._cli_path: str = ""
        self._timeout: int = 60
        self._max_output: int = 10 * 1024 * 1024
        self._allowed_paths: list[str] = []
        self._commands: dict[str, dict] = {}
    
    @property
    def adapter_type(self) -> str:
        return "cli_anything"
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            discovery=True,
            bidirectional=False,
            health_check=True,
            batch_operations=False,
        )
    
    async def initialize(self) -> None:
        cli_name = self.config.get("cli_name")
        cli_path = self.config.get("cli_path") or shutil.which(cli_name)
        
        if not cli_path:
            raise AdapterInitError(f"CLI-Anything command not found: {cli_name}")
        
        self._cli_path = cli_path
        self._timeout = int(self.config.get("timeout_seconds", 60))
        self._max_output = int(self.config.get("max_output_size", 10485760))
        self._allowed_paths = self.config.get("allowed_paths", ["/tmp"])
        
        result = await self._run_cli(["--version"])
        if result.returncode != 0:
            raise AdapterInitError(f"CLI test failed: {result.stderr}")
        
        await self._discover_commands()
    
    async def shutdown(self) -> None:
        pass
    
    async def _run_cli(
        self,
        args: list[str],
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        cmd = [self._cli_path] + args
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout or self._timeout,
            )
            
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=proc.returncode,
                stdout=stdout.decode(),
                stderr=stderr.decode(),
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise
    
    async def _discover_commands(self) -> None:
        result = await self._run_cli(["--list-commands", "--json"])
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                self._commands = {
                    cmd["name"]: cmd 
                    for cmd in data.get("commands", [])
                }
                return
            except json.JSONDecodeError:
                pass
        
        result = await self._run_cli(["--help"])
        self._commands = self._parse_help_output(result.stdout)
    
    def _parse_help_output(self, help_text: str) -> dict[str, dict]:
        commands = {}
        for line in help_text.split("\n"):
            if line.strip() and not line.startswith(" " * 4):
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    name, desc = parts
                    commands[name] = {
                        "name": name,
                        "description": desc,
                        "parameters": [],
                    }
        return commands
    
    async def discover_tools(self) -> list[ToolDefinition]:
        tools = []
        
        for cmd_name, cmd_info in self._commands.items():
            properties = {}
            required = []
            
            for param in cmd_info.get("parameters", []):
                param_name = param["name"].lstrip("-")
                properties[param_name] = {
                    "type": param.get("type", "string"),
                    "description": param.get("description", ""),
                }
                if param.get("required"):
                    required.append(param_name)
            
            tools.append(ToolDefinition(
                name=f"{self.name}.{cmd_name}",
                display_name=cmd_info.get("display_name", cmd_name),
                description=cmd_info.get("description", ""),
                input_schema={
                    "type": "object",
                    "properties": properties,
                    "required": required if required else None,
                },
                required_permissions=[f"{self.name}:execute"],
                metadata={
                    "cli_command": cmd_name,
                    "cli_adapter": self.name,
                    "timeout_seconds": self._timeout,
                },
            ))
        
        return tools
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> ToolResult:
        start_ms = context.get("start_time_ms", 0)
        
        cmd_args = [tool_name]
        
        for key, value in arguments.items():
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    cmd_args.append(flag)
            else:
                cmd_args.extend([flag, str(value)])
        
        try:
            result = await self._run_cli(cmd_args + ["--json"])
            
            output = None
            if result.stdout:
                try:
                    output = json.loads(result.stdout)
                except json.JSONDecodeError:
                    output = {"raw": result.stdout}
            
            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    result=output,
                    duration_ms=int(time.monotonic() * 1000) - start_ms,
                )
            else:
                return ToolResult(
                    success=False,
                    error=result.stderr or f"Exit code {result.returncode}",
                    result=output,
                    duration_ms=int(time.monotonic() * 1000) - start_ms,
                )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Timeout after {self._timeout}s",
                duration_ms=int(time.monotonic() * 1000) - start_ms,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                duration_ms=int(time.monotonic() * 1000) - start_ms,
            )
    
    async def execute_tool_stream(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> AsyncIterator[StreamChunk]:
        cmd_args = [tool_name]
        
        for key, value in arguments.items():
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    cmd_args.append(flag)
            else:
                cmd_args.extend([flag, str(value)])
        
        stream_prefix = self.config.get("stream_line_prefix", "STREAM:")
        if stream_prefix:
            cmd_args.extend(["--stream-prefix", stream_prefix])
        
        proc = await asyncio.create_subprocess_exec(
            self._cli_path,
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            while True:
                line = await asyncio.wait_for(
                    proc.stdout.readline(),
                    timeout=self._timeout,
                )
                
                if not line:
                    break
                
                line_str = line.decode().rstrip()
                
                if stream_prefix and line_str.startswith(stream_prefix):
                    content = line_str[len(stream_prefix):].strip()
                    try:
                        data = json.loads(content)
                        yield StreamChunk(chunk_type="content", content=data)
                    except json.JSONDecodeError:
                        yield StreamChunk(chunk_type="content", content=content)
                else:
                    yield StreamChunk(chunk_type="content", content=line_str)
            
            await proc.wait()
            
            if proc.returncode != 0:
                stderr = await proc.stderr.read()
                yield StreamChunk(chunk_type="error", content=stderr.decode())
            
            yield StreamChunk(chunk_type="done", content="")
        except asyncio.TimeoutError:
            proc.kill()
            yield StreamChunk(chunk_type="error", content=f"Timeout after {self._timeout}s")
            yield StreamChunk(chunk_type="done", content="")
    
    async def health_check(self) -> HealthCheckResult:
        import time
        from datetime import datetime, timezone
        
        start = time.monotonic()
        
        try:
            result = await self._run_cli(["--version"], timeout=5)
            latency_ms = int((time.monotonic() - start) * 1000)
            
            if result.returncode == 0:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    message=result.stdout.strip(),
                    last_check=datetime.now(timezone.utc),
                    latency_ms=latency_ms,
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=result.stderr,
                    last_check=datetime.now(timezone.utc),
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(exc),
                last_check=datetime.now(timezone.utc),
                latency_ms=int((time.monotonic() - start) * 1000),
            )
```

---

## 6. Plugin SDK

### 6.1 SDK Package Structure

```
integrations/sdk/
├── __init__.py              # Public API exports
├── base.py                  # BaseAdapter, BaseHTTPAdapter
├── testing.py               # Test utilities
├── templates/
│   └── minimal_adapter/     # Cookiecutter template
└── examples/
    ├── custom_crm_adapter.py
    └── database_adapter.py
```

### 6.2 SDK Public API

**File:** `integrations/sdk/base.py`

```python
"""AgentOS Integration SDK — Create custom adapters with minimal boilerplate."""

from typing import Any, Callable, Type

from integrations.core.adapter import (
    AdapterCapabilities,
    AdapterInitError,
    HealthCheckResult,
    HealthStatus,
    IntegrationAdapter,
    StreamChunk,
    ToolDefinition,
    ToolResult,
)


class BaseAdapter(IntegrationAdapter):
    """Simplified base class for SDK users."""
    
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        self._tools: list[ToolDefinition] = []
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=False,
            discovery=True,
            bidirectional=False,
            health_check=True,
            batch_operations=False,
        )
    
    async def discover_tools(self) -> list[ToolDefinition]:
        return self._tools
    
    def register_tool(self, tool: ToolDefinition) -> None:
        tool.name = f"{self.name}.{tool.name.split('.')[-1]}"
        self._tools.append(tool)
    
    async def health_check(self) -> HealthCheckResult:
        from datetime import datetime, timezone
        
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            last_check=datetime.now(timezone.utc),
            latency_ms=0,
        )
    
    def success(self, result: Any, duration_ms: int = 0) -> ToolResult:
        return ToolResult(success=True, result=result, duration_ms=duration_ms)
    
    def error(self, message: str, duration_ms: int = 0) -> ToolResult:
        return ToolResult(success=False, error=message, duration_ms=duration_ms)


class BaseHTTPAdapter(BaseAdapter):
    """Base class for HTTP-based adapters."""
    
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name, config)
        self._base_url: str = ""
        self._client: Any = None
    
    async def initialize(self) -> None:
        import httpx
        
        self._base_url = self.config.get("base_url", "").rstrip("/")
        if not self._base_url:
            raise AdapterInitError("HTTP adapter requires 'base_url'")
        
        headers = {"Accept": "application/json"}
        auth_type = self.config.get("auth_type", "none")
        auth_config = self.config.get("auth_config", {})
        
        if auth_type == "bearer":
            token = auth_config.get("token")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            header = auth_config.get("header", "X-API-Key")
            key = auth_config.get("key")
            if key:
                headers[header] = key
        
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=float(self.config.get("timeout", 30.0)),
        )
    
    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
    
    async def http_get(self, path: str, **kwargs) -> dict[str, Any]:
        response = await self._client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()
    
    async def http_post(self, path: str, **kwargs) -> dict[str, Any]:
        response = await self._client.post(path, **kwargs)
        response.raise_for_status()
        return response.json()


__all__ = [
    "BaseAdapter",
    "BaseHTTPAdapter",
    "AdapterCapabilities",
    "AdapterInitError",
    "HealthCheckResult",
    "HealthStatus",
    "StreamChunk",
    "ToolDefinition",
    "ToolResult",
]
```

### 6.3 Plugin Registration

Third-party adapters register via Python entry points:

```toml
# pyproject.toml
[project.entry-points."agentos.adapters"]
custom_crm = "my_crm_adapter:CustomCRMAdapter"
slack = "slack_adapter:SlackAdapter"
```

---

## 7. Configuration and Registry

### 7.1 Configuration Schemas

**File:** `integrations/core/config.py`

```python
"""Integration configuration schemas and validation."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AdapterConfig(BaseModel):
    """Base configuration for any adapter."""
    
    name: str = Field(..., min_length=1, max_length=64)
    adapter_type: str = Field(..., min_length=1)
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    required_permissions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MCPAdapterConfig(AdapterConfig):
    adapter_type: Literal["mcp"] = "mcp"
    
    @field_validator("config")
    @classmethod
    def validate_mcp_config(cls, v: dict[str, Any]) -> dict[str, Any]:
        if "url" not in v:
            raise ValueError("MCP config requires 'url'")
        return v


class RESTAdapterConfig(AdapterConfig):
    adapter_type: Literal["rest"] = "rest"
    
    @field_validator("config")
    @classmethod
    def validate_rest_config(cls, v: dict[str, Any]) -> dict[str, Any]:
        if "base_url" not in v:
            raise ValueError("REST config requires 'base_url'")
        return v
```

### 7.2 Integration Registry

**File:** `integrations/core/registry.py`

```python
"""Integration Registry — Manages adapter lifecycle and tool discovery."""

from typing import Any

import structlog

from integrations.core.adapter import IntegrationAdapter
from integrations.core.security import SecureAdapterWrapper

logger = structlog.get_logger(__name__)


class IntegrationRegistry:
    """Central registry for all integration adapters."""
    
    def __init__(self) -> None:
        self._adapters: dict[str, SecureAdapterWrapper] = {}
        self._tool_index: dict[str, str] = {}
    
    async def register_adapter(
        self,
        config: AdapterConfig,
        adapter_class: type[IntegrationAdapter] | None = None,
    ) -> SecureAdapterWrapper:
        if config.name in self._adapters:
            raise ValueError(f"Adapter '{config.name}' already registered")
        
        if adapter_class is None:
            adapter_class = self._get_adapter_class(config.adapter_type)
        
        raw_adapter = adapter_class(config.name, config.config)
        secure_adapter = SecureAdapterWrapper(raw_adapter)
        
        await secure_adapter.initialize()
        
        tools = await secure_adapter.discover_tools()
        for tool in tools:
            self._tool_index[tool.name] = config.name
        
        self._adapters[config.name] = secure_adapter
        
        logger.info(
            "adapter_registered",
            name=config.name,
            type=config.adapter_type,
            tools=len(tools),
        )
        
        return secure_adapter
    
    def _get_adapter_class(self, adapter_type: str) -> type[IntegrationAdapter]:
        from integrations.adapters.mcp.adapter import MCPAdapter
        from integrations.adapters.rest.adapter import RESTAdapter
        from integrations.adapters.webhook.adapter import WebhookAdapter
        from integrations.adapters.cli_anything.adapter import CLIAnythingAdapter
        
        mapping = {
            "mcp": MCPAdapter,
            "rest": RESTAdapter,
            "webhook": WebhookAdapter,
            "cli_anything": CLIAnythingAdapter,
        }
        
        if adapter_type not in mapping:
            plugins = discover_plugins()
            if adapter_type in plugins:
                return plugins[adapter_type]
            raise ValueError(f"Unknown adapter type: {adapter_type}")
        
        return mapping[adapter_type]
    
    async def get_tool_adapter(
        self,
        tool_fqn: str,
    ) -> SecureAdapterWrapper | None:
        adapter_name = self._tool_index.get(tool_fqn)
        if not adapter_name:
            return None
        return self._adapters.get(adapter_name)
    
    async def list_all_tools(self) -> list[ToolDefinition]:
        all_tools = []
        for adapter in self._adapters.values():
            tools = await adapter.discover_tools()
            all_tools.extend(tools)
        return all_tools


# Global registry instance
registry = IntegrationRegistry()
```

---

## 8. Database Schema

### 8.1 New Table for Adapter Configurations

```sql
-- Adapter configurations for Universal Integration Framework
CREATE TABLE adapter_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(64) NOT NULL UNIQUE,
    adapter_type VARCHAR(32) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    config JSONB NOT NULL DEFAULT '{}',
    required_permissions TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID NOT NULL
);

-- Indexes for fast lookup
CREATE INDEX idx_adapter_configs_type ON adapter_configs(adapter_type);
CREATE INDEX idx_adapter_configs_enabled ON adapter_configs(enabled);

-- Migration: Existing MCP servers can be migrated to adapter_configs
-- INSERT INTO adapter_configs (name, adapter_type, config, ...)
-- SELECT name, 'mcp', jsonb_build_object('url', url, ...), ...
-- FROM registry_entries WHERE type = 'mcp_server';
```

---

## 9. Migration from Existing Code

### 9.1 Migration Strategy

| Existing Component | New Component | Migration Approach |
|-------------------|---------------|-------------------|
| `backend/mcp/client.py` | `integrations/adapters/mcp/adapter.py` | Refactor, keep interface compatible |
| `backend/mcp/registry.py` | `integrations/core/registry.py` | Deprecate, use IntegrationRegistry |
| `backend/openapi_bridge/service.py` | `integrations/adapters/rest/openapi.py` | Extract, extend RESTAdapter |
| `registry_entries` table | `adapter_configs` + `registry_entries` | Dual-write during transition |

### 9.2 Backward Compatibility

```python
# During migration phase, support both old and new
async def call_tool_legacy(tool_name: str, ...):
    """Legacy path for existing code."""
    # Check if tool is registered via new framework
    adapter = await registry.get_tool_adapter(tool_name)
    if adapter:
        return await adapter.execute(...)
    
    # Fallback to legacy path
    return await call_mcp_tool_legacy(tool_name, ...)
```

---

## 10. Implementation Phases

### Phase 1: Core Framework (2 weeks)
- [ ] Create `integrations/` module structure
- [ ] Implement Adapter Protocol (`integrations/core/adapter.py`)
- [ ] Implement SecureAdapterWrapper (`integrations/core/security.py`)
- [ ] Implement IntegrationRegistry (`integrations/core/registry.py`)
- [ ] Configuration schemas and validation
- [ ] Database migration for `adapter_configs` table

### Phase 2: MCP Adapter Refactor (1 week)
- [ ] Refactor existing MCP client into MCPAdapter
- [ ] Ensure backward compatibility with existing registry_entries
- [ ] Add comprehensive tests
- [ ] Performance benchmarking

### Phase 3: REST & Webhook Adapters (1 week)
- [ ] Implement RESTAdapter (manual config)
- [ ] Implement OpenAPIAdapter (spec-driven)
- [ ] Implement WebhookAdapter with HMAC verification
- [ ] Webhook HTTP endpoint registration

### Phase 4: CLI-Anything Adapter (1 week)
- [ ] Implement CLIAnythingAdapter with subprocess wrapper
- [ ] Line-by-line streaming support
- [ ] Filesystem path validation
- [ ] Test with cli-anything-libreoffice

### Phase 5: Plugin SDK & Polish (1 week)
- [ ] Create Plugin SDK (`integrations/sdk/`)
- [ ] BaseAdapter and BaseHTTPAdapter
- [ ] Testing utilities
- [ ] Cookiecutter template
- [ ] Documentation and examples
- [ ] Migration guide from existing code

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# Test each adapter in isolation
async def test_mcp_adapter():
    adapter = MCPAdapter("test", {"url": "http://localhost:8000"})
    await adapter.initialize()
    
    tools = await adapter.discover_tools()
    assert len(tools) > 0
    
    result = await adapter.execute_tool("test_tool", {"arg": "value"}, {})
    assert result.success

async def test_security_wrapper():
    mock_adapter = MockAdapter()
    secure = SecureAdapterWrapper(mock_adapter)
    
    # Test RBAC gate
    with pytest.raises(HTTPException) as exc:
        await secure.execute(..., security_context_without_permission)
    assert exc.value.status_code == 403
```

### 11.2 Integration Tests

```python
# Test full flow with real services
async def test_mcp_integration():
    # Start test MCP server
    # Register adapter
    # Execute tool through full stack
    pass

async def test_cli_anything_integration():
    # Install cli-anything-echo
    # Register adapter
    # Execute echo command
    pass
```

### 11.3 Security Tests

```python
async def test_cli_path_validation():
    # Attempt to access /etc/passwd
    # Verify 403 response
    pass

async def test_webhook_signature():
    # Send webhook with invalid signature
    # Verify rejection
    pass
```

---

## 12. Open Questions & Future Work

### 12.1 Open Questions

1. **OAuth2 Flow**: Should the REST adapter handle OAuth2 token refresh, or leave to external OAuth2 proxy?
2. **Rate Limiting**: Should rate limiting be in SecureAdapterWrapper or individual adapters?
3. **Circuit Breaker**: Should we implement circuit breaker pattern for failing adapters?
4. **Caching**: Should tool discovery results be cached, or always fresh?

### 12.2 Future Work

- **GraphQL Adapter**: Support GraphQL APIs with introspection
- **gRPC Adapter**: Support gRPC services with protobuf
- **Message Queue Adapter**: Support RabbitMQ, Kafka, etc.
- **Caching Layer**: Cache tool discovery and health checks
- **Metrics**: Per-adapter metrics (calls, latency, errors)

### 12.3 MCP vs CLI-Anything Resolution

This design **resolves the deferred MCP vs CLI-Anything discussion** by:

1. **Supporting both** through the unified adapter framework
2. **Different use cases**:
   - MCP: Custom-built tools, real-time streaming, integrated security
   - CLI-Anything: Existing software (LibreOffice, GIMP), zero dev effort
3. **Consistent security**: Both go through identical 3-gate security
4. **Future extensibility**: Easy to add new integration types

---

## Appendix A: File Structure

```
integrations/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── adapter.py          # IntegrationAdapter protocol
│   ├── security.py         # SecureAdapterWrapper
│   ├── registry.py         # IntegrationRegistry
│   └── config.py           # Configuration schemas
├── adapters/
│   ├── __init__.py
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── adapter.py      # MCPAdapter
│   ├── rest/
│   │   ├── __init__.py
│   │   ├── base.py         # BaseHTTPAdapter
│   │   ├── adapter.py      # RESTAdapter
│   │   └── openapi.py      # OpenAPIAdapter
│   ├── webhook/
│   │   ├── __init__.py
│   │   └── adapter.py      # WebhookAdapter
│   └── cli_anything/
│       ├── __init__.py
│       └── adapter.py      # CLIAnythingAdapter
└── sdk/
    ├── __init__.py
    ├── base.py             # BaseAdapter, BaseHTTPAdapter
    ├── testing.py          # Test utilities
    └── templates/
        └── minimal_adapter/
            ├── {{adapter_name}}/
            │   ├── __init__.py
            │   └── adapter.py
            └── pyproject.toml
```

---

*Design complete. Ready for implementation planning.*
