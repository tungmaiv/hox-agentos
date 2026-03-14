# Admin Console LLM Configuration

**Status:** ✅ Design Complete  
**Priority:** High  
**Target:** v1.4  
**Estimated Effort:** 2-3 weeks  
**Last Updated:** 2026-03-14

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Architecture](#architecture)
4. [Base Module Framework](#base-module-framework)
5. [LiteLLM Config Module](#litellm-config-module)
6. [Admin Console UI](#admin-console-ui)
7. [Database Schema](#database-schema)
8. [Implementation Phases](#implementation-phases)
9. [Success Criteria](#success-criteria)
10. [Risks and Mitigations](#risks-and-mitigations)
11. [Future Enhancements](#future-enhancements)

---

## Executive Summary

This enhancement transforms LiteLLM configuration from a file-based, restart-required workflow into a dynamic, UI-driven operational experience. By introducing a **pluggable module architecture** with CLI-based backends, we enable runtime model management, fallback chain configuration, health monitoring, and cost tracking—all from the Admin Console.

### Key Innovation: Generic Module Pattern

The architecture introduces a `BaseModule` abstract class that any AgentOS feature can inherit. This pattern decouples functionality from the core backend, enabling:
- **Independent upgrades** of modules without full system restart
- **Technology diversity** (Python, Node, Go) per module
- **Horizontal scaling** at the module level
- **Reusable pattern** for future features (Security Scanner, Analytics, etc.)

---

## Problem Statement

### Current State (As-Is)

| Aspect | Current Reality | Pain Point |
|--------|----------------|------------|
| **Model Changes** | Edit `infra/litellm/config.yaml` | Requires SSH/container access |
| **Apply Changes** | Restart LiteLLM container | Downtime, service interruption |
| **Add Models** | Manual YAML editing | Error-prone, no validation |
| **Testing** | Manual API calls to LiteLLM | No integrated test workflow |
| **Monitoring** | Check LiteLLM logs manually | No visibility into model health |
| **Cost Tracking** | Not available | No budget awareness |
| **Fallbacks** | Static YAML configuration | No runtime adjustment |

### Target State (To-Be)

| Aspect | Target Experience | Benefit |
|--------|------------------|---------|
| **Model Changes** | Admin UI with forms | No file editing, instant feedback |
| **Apply Changes** | Runtime via API | Zero downtime |
| **Add Models** | Wizard with validation | Guided, error-proof |
| **Testing** | One-click connectivity test | Confidence before saving |
| **Monitoring** | Real-time health dashboard | Proactive issue detection |
| **Cost Tracking** | Usage charts + budget alerts | Financial control |
| **Fallbacks** | Visual chain builder | Dynamic, condition-based |

---

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Compose / Kubernetes                  │
│                                                                 │
│  ┌─────────────────┐        ┌────────────────────────────────┐  │
│  │  Backend        │◀──────▶│  Module Sidecars (1-N replicas)│  │
│  │  ┌───────────┐  │ HTTP   │  ┌──────────────────────────┐  │  │
│  │  │BaseClient │  │        │  │  BaseModule (abstract)   │  │  │
│  │  │ - HTTP    │  │        │  │  ┌──────────────────┐    │  │  │
│  │  │ - Circuit │  │        │  │  │ execute_cli()    │    │  │  │
│  │  │   breaker │  │        │  │  │ health_check()   │    │  │  │
│  │  │ - Retry   │  │        │  │  │ metrics()        │    │  │  │
│  │  └───────────┘  │        │  │  └──────────────────┘    │  │  │
│  └─────────────────┘        │  │  ┌──────────────────┐    │  │  │
│          │                  │  │  │ Custom Methods   │    │  │  │
│          ▼                  │  │  │ (overrideable)   │    │  │  │
│  ┌─────────────────┐        │  │  └──────────────────┘    │  │  │
│  │ Module Registry │        │  └──────────────────────────┘  │  │
│  │  (Redis/etcd)   │        │                                │  │
│  └─────────────────┘        └────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Sidecar Services                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │   │
│  │  │ litellm-     │  │ security-    │  │   [Future]     │  │   │
│  │  │ config       │  │ scanner      │  │   modules      │  │   │
│  │  │ :8000        │  │ :8000        │  │   :8000        │  │   │
│  │  └──────────────┘  └──────────────┘  └────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Scale Considerations

| Scale | Users | Infrastructure | Module Deployment |
|-------|-------|----------------|-------------------|
| **MVP** | 100 | Docker Compose | Sidecars in compose file |
| **Growth** | 500 | Docker Swarm | Sidecars with replicas |
| **Scale** | 2,000+ | Kubernetes | Deployments with HPA |

**Migration Path:** The module code remains identical across all scales. Only the orchestration changes (compose → swarm → k8s).

---

## Base Module Framework

### Abstract Base Class

```python
# backend/modules/base/module.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel
import asyncio
import subprocess

class CliResult(BaseModel):
    """Result of CLI command execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int

class ModuleHealth(BaseModel):
    """Module health status."""
    healthy: bool
    version: str
    uptime_seconds: int
    message: Optional[str] = None

class BaseModule(ABC):
    """
    Abstract base for all AgentOS CLI modules.
    
    Modules inherit this class and implement:
    - module_name: Unique identifier
    - module_version: Semantic version
    - get_commands(): Available CLI commands
    - health_check(): Health verification
    
    Optional overrides:
    - execute(): Custom command handling
    - metrics(): Custom metrics collection
    """
    
    def __init__(self):
        self._command_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
    
    @property
    @abstractmethod
    def module_name(self) -> str:
        """Unique module identifier (e.g., 'litellm-config')."""
        pass
    
    @property
    @abstractmethod
    def module_version(self) -> str:
        """Module version (e.g., '1.0.0')."""
        pass
    
    @abstractmethod
    def get_commands(self) -> List[Dict[str, Any]]:
        """
        Return list of available CLI commands.
        
        Returns:
            List of command definitions with args schema:
            [
                {
                    "name": "add_model",
                    "description": "Add a new LLM model",
                    "args": {
                        "name": {"type": "string", "required": True},
                        "provider": {"type": "string", "required": True}
                    }
                }
            ]
        """
        pass
    
    def _register_default_handlers(self):
        """Register custom command handlers. Override in subclass."""
        pass
    
    async def execute(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command.
        
        Default implementation runs CLI directly.
        Override for custom logic: validation, caching, transformation.
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            Execution result with success/error details
        """
        handler = self._command_handlers.get(command)
        if handler:
            return await handler(args)
        return await self._execute_cli(command, args)
    
    async def _execute_cli(
        self, 
        command: str, 
        args: Dict[str, Any],
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Execute CLI command with proper error handling.
        
        Args:
            command: CLI command name
            args: Command arguments
            timeout: Maximum execution time in seconds
            
        Returns:
            CliResult as dict with exit_code, stdout, stderr, duration_ms
        """
        cmd = self._build_command(command, args)
        
        start = asyncio.get_event_loop().time()
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), 
                timeout=timeout
            )
            duration_ms = int((asyncio.get_event_loop().time() - start) * 1000)
            
            return CliResult(
                exit_code=proc.returncode,
                stdout=stdout.decode().strip(),
                stderr=stderr.decode().strip(),
                duration_ms=duration_ms
            ).dict()
        except asyncio.TimeoutError:
            return {
                "error": f"Command timed out after {timeout}s",
                "exit_code": -1,
                "duration_ms": timeout * 1000
            }
        except Exception as e:
            return {
                "error": str(e),
                "exit_code": -1,
                "duration_ms": int((asyncio.get_event_loop().time() - start) * 1000)
            }
    
    def _build_command(self, command: str, args: Dict[str, Any]) -> str:
        """Build CLI command string from args."""
        cmd_parts = [command]
        for key, value in args.items():
            if isinstance(value, bool) and value:
                cmd_parts.append(f"--{key}")
            elif value is not None:
                cmd_parts.append(f"--{key}={value}")
        return " ".join(cmd_parts)
    
    @abstractmethod
    async def health_check(self) -> ModuleHealth:
        """
        Return module health status.
        
        Returns:
            ModuleHealth with healthy flag and diagnostic info
        """
        pass
    
    async def metrics(self) -> Dict[str, Any]:
        """
        Return module metrics. Override for custom metrics.
        
        Returns:
            Dictionary of metric key-value pairs
        """
        return {}
```

### Module Client (Backend)

```python
# backend/modules/base/client.py
import aiohttp
from typing import Dict, Any
from backend.modules.base.circuit_breaker import CircuitBreaker
from backend.modules.base.retry import RetryPolicy

class ModuleClient:
    """
    Client for calling module sidecars with resilience patterns.
    
    Features:
    - Circuit breaker: Fail fast if module is down
    - Retry policy: Exponential backoff for transient failures
    - Timeout handling: Configurable per-call timeouts
    """
    
    def __init__(self, module_url: str):
        self.url = module_url
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30
        )
        self.retry_policy = RetryPolicy(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0
        )
    
    async def execute(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command with circuit breaker and retry."""
        async with self.circuit_breaker:
            async with self.retry_policy:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.url}/execute",
                        json={"command": command, "args": args},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status != 200:
                            error = await resp.text()
                            raise ModuleError(f"Command failed: {error}")
                        return await resp.json()
    
    async def list_commands(self) -> Dict[str, Any]:
        """List available commands."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.url}/commands") as resp:
                return await resp.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check module health."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.url}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return await resp.json()
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get module metrics."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.url}/metrics") as resp:
                return await resp.json()

class ModuleError(Exception):
    """Module communication error."""
    pass
```

### Module Registry

```python
# backend/modules/base/registry.py
import json
import redis.asyncio as redis
from typing import Dict, Any, List, Optional
from datetime import datetime

class ModuleRegistry:
    """
    Redis-backed module registry for dynamic discovery.
    
    Modules register themselves on startup.
    Backend discovers available modules from registry.
    """
    
    REDIS_KEY = "agentos:modules"
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or redis.from_url(
            "redis://redis:6379",
            decode_responses=True
        )
    
    async def register(
        self, 
        module_name: str, 
        url: str, 
        metadata: Dict[str, Any]
    ):
        """Register a module."""
        await self.redis.hset(
            self.REDIS_KEY,
            module_name,
            json.dumps({
                "name": module_name,
                "url": url,
                "metadata": metadata,
                "registered_at": datetime.utcnow().isoformat(),
                "health": "unknown"
            })
        )
    
    async def unregister(self, module_name: str):
        """Unregister a module."""
        await self.redis.hdel(self.REDIS_KEY, module_name)
    
    async def get_module(self, name: str) -> Optional[Dict[str, Any]]:
        """Get module by name."""
        data = await self.redis.hget(self.REDIS_KEY, name)
        return json.loads(data) if data else None
    
    async def list_modules(self) -> List[Dict[str, Any]]:
        """List all registered modules."""
        modules = await self.redis.hgetall(self.REDIS_KEY)
        return [json.loads(m) for m in modules.values()]
    
    async def update_health(self, module_name: str, health: str):
        """Update module health status."""
        module = await self.get_module(module_name)
        if module:
            module["health"] = health
            module["health_updated_at"] = datetime.utcnow().isoformat()
            await self.redis.hset(
                self.REDIS_KEY, 
                module_name, 
                json.dumps(module)
            )
```

---

## LiteLLM Config Module

### Module Implementation

```python
# backend/modules/litellm_config/module.py
from typing import Dict, Any, List
import json
from backend.modules.base.module import BaseModule, ModuleHealth

class LitellmConfigModule(BaseModule):
    """
    LiteLLM configuration management module.
    
    Manages LiteLLM proxy configuration including:
    - Model add/remove/list
    - Model testing
    - Health monitoring
    - Metrics collection
    """
    
    @property
    def module_name(self) -> str:
        return "litellm-config"
    
    @property
    def module_version(self) -> str:
        return "1.0.0"
    
    def __init__(self):
        super().__init__()
        self._litellm_proxy_url = "http://litellm:4000"
    
    def _register_default_handlers(self):
        """Register custom command handlers."""
        self._command_handlers["add_model"] = self._handle_add_model
        self._command_handlers["list_models"] = self._handle_list_models
        self._command_handlers["get_model_health"] = self._handle_get_health
        self._command_handlers["get_metrics"] = self._handle_get_metrics
    
    def get_commands(self) -> List[Dict[str, Any]]:
        """Return available commands."""
        return [
            {
                "name": "add_model",
                "description": "Add a new LLM model",
                "args": {
                    "name": {"type": "string", "required": True},
                    "provider": {"type": "string", "required": True},
                    "model": {"type": "string", "required": True},
                    "api_base": {"type": "string", "required": False},
                    "api_key": {"type": "string", "required": False, "secret": True},
                    "temperature": {"type": "number", "default": 0.7},
                    "max_tokens": {"type": "integer", "required": False},
                    "rpm_limit": {"type": "integer", "required": False},
                    "tpm_limit": {"type": "integer", "required": False},
                    "tags": {"type": "array", "items": "string"}
                }
            },
            {
                "name": "remove_model",
                "description": "Remove an LLM model",
                "args": {
                    "name": {"type": "string", "required": True}
                }
            },
            {
                "name": "list_models",
                "description": "List all configured models",
                "args": {}
            },
            {
                "name": "test_model",
                "description": "Test model connectivity",
                "args": {
                    "name": {"type": "string", "required": True}
                }
            },
            {
                "name": "update_model",
                "description": "Update model configuration",
                "args": {
                    "name": {"type": "string", "required": True},
                    "temperature": {"type": "number", "required": False},
                    "max_tokens": {"type": "integer", "required": False},
                    "rpm_limit": {"type": "integer", "required": False},
                    "tpm_limit": {"type": "integer", "required": False}
                }
            },
            {
                "name": "get_model_health",
                "description": "Get health status for a model",
                "args": {
                    "name": {"type": "string", "required": True}
                }
            },
            {
                "name": "get_metrics",
                "description": "Get usage metrics",
                "args": {
                    "name": {"type": "string", "required": False},
                    "period": {"type": "string", "enum": ["1h", "24h", "7d", "30d"], "default": "24h"}
                }
            }
        ]
    
    async def _handle_add_model(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add model with validation."""
        # Check for duplicates
        existing = await self._get_existing_models()
        if args["name"] in existing:
            return {
                "success": False,
                "error": f"Model '{args['name']}' already exists"
            }
        
        # Validate provider
        valid_providers = ["openai", "anthropic", "ollama", "openrouter", "azure", "cohere"]
        if args["provider"] not in valid_providers:
            return {
                "success": False,
                "error": f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
            }
        
        # Execute CLI
        result = await self._execute_cli("litellm-model add", args)
        
        if result["exit_code"] == 0:
            return {
                "success": True,
                "data": {
                    "name": args["name"],
                    "provider": args["provider"],
                    "added_at": self._get_timestamp()
                },
                "cli_result": result
            }
        else:
            return {
                "success": False,
                "error": result["stderr"] or "Unknown error",
                "cli_result": result
            }
    
    async def _handle_list_models(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List and enrich models."""
        result = await self._execute_cli("litellm-model list", args)
        
        if result["exit_code"] != 0:
            return {"success": False, "error": result["stderr"]}
        
        try:
            models = json.loads(result["stdout"])
            enriched = []
            for model in models:
                model["health"] = await self._get_model_health(model["model_name"])
                enriched.append(model)
            
            return {
                "success": True,
                "data": {"models": enriched, "count": len(enriched)},
                "cli_result": result
            }
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Failed to parse model list",
                "cli_result": result
            }
    
    async def _handle_get_health(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get model health."""
        model_name = args["name"]
        health = await self._get_model_health(model_name)
        return {
            "success": True,
            "data": health
        }
    
    async def _handle_get_metrics(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get aggregated metrics."""
        model_name = args.get("name")
        period = args.get("period", "24h")
        
        # Fetch from LiteLLM Prometheus or internal API
        metrics = await self._fetch_metrics(model_name, period)
        
        return {
            "success": True,
            "data": metrics
        }
    
    async def health_check(self) -> ModuleHealth:
        """Check LiteLLM proxy health."""
        try:
            result = await self._execute_cli("litellm health", {}, timeout=5)
            if result["exit_code"] == 0:
                return ModuleHealth(
                    healthy=True,
                    version="1.0.0",
                    uptime_seconds=3600,
                    message="LiteLLM proxy reachable"
                )
            else:
                return ModuleHealth(
                    healthy=False,
                    version="1.0.0",
                    uptime_seconds=0,
                    message="LiteLLM proxy not responding"
                )
        except Exception as e:
            return ModuleHealth(
                healthy=False,
                version="1.0.0",
                uptime_seconds=0,
                message=str(e)
            )
    
    async def _get_existing_models(self) -> List[str]:
        """Helper: Get existing model names."""
        result = await self._execute_cli("litellm-model list", {})
        if result["exit_code"] == 0:
            try:
                models = json.loads(result["stdout"])
                return [m["model_name"] for m in models]
            except:
                pass
        return []
    
    async def _get_model_health(self, model_name: str) -> Dict[str, Any]:
        """Helper: Get health for specific model."""
        # Query LiteLLM or cache
        return {
            "model": model_name,
            "healthy": True,
            "latency_ms": 45,
            "success_rate": 0.999,
            "last_check": self._get_timestamp()
        }
    
    async def _fetch_metrics(self, model_name: Optional[str], period: str) -> Dict[str, Any]:
        """Helper: Fetch metrics from LiteLLM."""
        return {
            "requests": 1250,
            "tokens_input": 45000,
            "tokens_output": 32000,
            "cost_usd": 12.50,
            "avg_latency_ms": 52,
            "period": period
        }
    
    def _get_timestamp(self) -> str:
        """Helper: Current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
```

### Sidecar FastAPI App

```python
# backend/modules/litellm_config/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from backend.modules.base.registry import ModuleRegistry
from .module import LitellmConfigModule

# Initialize module
module = LitellmConfigModule()
registry = ModuleRegistry()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Register with backend
    await registry.register(
        module.module_name,
        f"http://{os.getenv('HOSTNAME', 'localhost')}:8000",
        {
            "version": module.module_version,
            "commands": len(module.get_commands())
        }
    )
    yield
    # Cleanup
    await registry.unregister(module.module_name)

app = FastAPI(
    title="LiteLLM Config Module",
    description="CLI-based LiteLLM configuration management",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    """Health check endpoint."""
    return await module.health_check()

@app.get("/commands")
async def list_commands():
    """List available commands."""
    return {
        "module": module.module_name,
        "version": module.module_version,
        "commands": module.get_commands()
    }

@app.post("/execute")
async def execute(request: dict):
    """Execute a command."""
    command = request.get("command")
    args = request.get("args", {})
    
    # Validate command
    valid_commands = [c["name"] for c in module.get_commands()]
    if command not in valid_commands:
        raise HTTPException(status_code=400, detail=f"Unknown command: {command}")
    
    # Execute
    result = await module.execute(command, args)
    
    if not result.get("success", True):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result

@app.get("/metrics")
async def metrics():
    """Get module metrics."""
    return await module.metrics()
```

### Dockerfile

```dockerfile
# backend/modules/litellm_config/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install LiteLLM CLI
RUN pip install litellm[proxy]

# Copy module code
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Admin Console UI

### Page Structure

```
/admin/llm-configuration
├── /models              # Model Management
├── /fallbacks           # Fallback Chains
├── /health              # Health Dashboard
└── /costs               # Cost Tracking
```

### Models Page (`/admin/llm-configuration/models`)

**Features:**
- List all configured models with search/filter
- Add/edit/remove models via modal forms
- One-click test connectivity
- Toggle active/paused status
- Dual pagination (top + bottom)

**Model List Columns:**
- Model Name (with tags)
- Provider (OpenAI, Anthropic, etc.)
- Status (Active/Paused)
- Health (latency, success rate)
- Actions (Configure, Test, Pause/Resume, Delete)

**Add Model Form Fields:**
```typescript
interface AddModelForm {
  name: string;              // Identifier
  display_name: string;      // Human-readable name
  provider: ProviderType;    // openai | anthropic | ollama | openrouter | azure
  model: string;             // Actual model ID
  api_base?: string;         // Custom endpoint
  api_key?: string;          // Encrypted storage
  temperature: number;       // 0.0 - 2.0
  max_tokens?: number;
  timeout_ms: number;        // Default: 30000
  rpm_limit?: number;        // Requests per minute
  tpm_limit?: number;        // Tokens per minute
  tags: string[];            // Categorization
}
```

### Fallbacks Page (`/admin/llm-configuration/fallbacks`)

**Features:**
- Visual fallback chain builder
- Drag-and-drop priority ordering
- Condition-based routing:
  - `timeout` — Response time exceeded
  - `rate_limited` — 429 errors
  - `error_rate` — High error percentage
  - `unavailable` — 5xx/connection failures
  - `always` — Always try this fallback

**Fallback Chain Structure:**
```typescript
interface FallbackChain {
  id: string;
  name: string;
  description?: string;
  is_default: boolean;
  steps: FallbackStep[];
}

interface FallbackStep {
  priority: number;
  model: string;
  condition: FallbackCondition;
  condition_value?: number;  // For timeout_ms or error_rate_threshold
}

type FallbackCondition = 
  | 'always'
  | 'timeout'
  | 'rate_limited' 
  | 'error_rate'
  | 'unavailable';
```

### Health Page (`/admin/llm-configuration/health`)

**Features:**
- Real-time health status cards (Healthy/Degraded/Critical/Unknown)
- Latency charts (last 24h, 7d, 30d)
- Success/error rate trends
- Model-by-model status table
- Auto-refresh toggle

**Health Metrics:**
- Response latency (p50, p95, p99)
- Success rate (%)
- Error breakdown by type
- Token throughput
- Rate limit hits per model

### Costs Page (`/admin/llm-configuration/costs`)

**Features:**
- Monthly cost overview with budget progress
- Cost by model (bar chart)
- Cost by day (line chart)
- Usage quotas table with alerts
- Export to CSV/PDF

**Quota Management:**
```typescript
interface ModelQuota {
  model_name: string;
  requests_limit?: number;      // Monthly request limit
  tokens_limit?: number;        // Monthly token limit
  cost_limit?: number;          // Monthly cost limit (USD)
  current_requests: number;
  current_tokens: number;
  current_cost: number;
  alert_threshold: number;      // Alert at % (e.g., 80)
  enforcement: 'hard' | 'soft'; // Hard = reject, Soft = warn
}
```

---

## Database Schema

### Module Metadata

```sql
-- Track registered modules
CREATE TABLE module_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_name VARCHAR(255) NOT NULL UNIQUE,
    module_version VARCHAR(50) NOT NULL,
    module_url VARCHAR(500) NOT NULL,
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    health_status VARCHAR(50) DEFAULT 'unknown',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_module_health ON module_metadata(health_status);
```

### Usage Statistics

```sql
-- Aggregated daily usage per model
CREATE TABLE llm_usage_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    request_count INTEGER DEFAULT 0,
    tokens_input BIGINT DEFAULT 0,
    tokens_output BIGINT DEFAULT 0,
    cost_usd DECIMAL(10, 4) DEFAULT 0.0,
    avg_latency_ms INTEGER,
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(model_name, date)
);

CREATE INDEX idx_usage_date ON llm_usage_stats(date);
CREATE INDEX idx_usage_model ON llm_usage_stats(model_name);
```

### Fallback Chains

```sql
-- Fallback chain configurations
CREATE TABLE fallback_chains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    config JSONB NOT NULL,  -- Array of {priority, model, condition}
    created_by UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_fallback_default ON fallback_chains(is_default) WHERE is_default = TRUE;
```

### Model Quotas

```sql
-- Quota settings per model
CREATE TABLE model_quotas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(255) NOT NULL UNIQUE,
    requests_limit INTEGER,
    tokens_limit BIGINT,
    cost_limit DECIMAL(10, 2),
    alert_threshold INTEGER DEFAULT 80,  -- Percentage
    enforcement VARCHAR(10) DEFAULT 'soft',  -- 'hard' | 'soft'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Implementation Phases

### Phase 1: Base Framework (Days 1-3)

**Tasks:**
1. Create `backend/modules/base/` with:
   - `module.py` - BaseModule abstract class
   - `client.py` - ModuleClient with resilience
   - `registry.py` - Redis-backed discovery
   - `circuit_breaker.py` - Circuit breaker pattern
   - `retry.py` - Retry policy
2. Write unit tests for base classes
3. Create module scaffolding CLI tool

**Deliverables:**
- Base module framework
- Test suite
- Documentation for creating new modules

### Phase 2: LiteLLM Module (Days 4-6)

**Tasks:**
1. Create `backend/modules/litellm_config/` structure
2. Implement LitellmConfigModule with all 7 commands
3. Build CLI wrapper scripts
4. Create Dockerfile and docker-compose service
5. Write integration tests

**Deliverables:**
- Working sidecar service
- 7 CLI commands implemented
- Docker image buildable
- Test coverage >80%

### Phase 3: Backend Integration (Days 7-8)

**Tasks:**
1. Add module discovery to backend startup
2. Create `/api/modules/{name}/execute` endpoint
3. Add admin permission checks
4. Implement error handling and logging
5. Add database migrations

**Deliverables:**
- Backend API routes
- Database schema
- Admin authorization
- API documentation

### Phase 4: Frontend Models Page (Days 9-11)

**Tasks:**
1. Create page layout with tabs
2. Build ModelList component with filters
3. Create AddModelModal with form validation
4. Implement test connectivity button
5. Add pagination and search

**Deliverables:**
- /admin/llm-configuration/models page
- Model CRUD operations
- Form validation
- Responsive design

### Phase 5: Frontend Fallbacks & Health (Days 12-14)

**Tasks:**
1. Build FallbackChainBuilder component
2. Create drag-and-drop priority ordering
3. Implement HealthDashboard with charts
4. Add real-time data fetching
5. Create health status indicators

**Deliverables:**
- Fallbacks page with chain builder
- Health dashboard with metrics
- Chart components
- Auto-refresh functionality

### Phase 6: Cost Tracking (Days 15-17)

**Tasks:**
1. Create CostTracking component
2. Build budget visualization
3. Implement quota management UI
4. Add export functionality
5. Create alert configuration

**Deliverables:**
- Cost tracking page
- Budget alerts
- Quota management
- Export features

### Phase 7: Integration & Docs (Days 18-21)

**Tasks:**
1. End-to-end testing
2. Performance testing
3. Write user documentation
4. Create admin guide
5. Record demo video

**Deliverables:**
- E2E test suite
- Documentation
- Admin guide
- Production-ready code

---

## Success Criteria

### Functional Requirements

- [ ] Add new LLM model via UI without restart
- [ ] Test model connectivity with one click
- [ ] Configure fallback chains visually
- [ ] View real-time model health status
- [ ] Track costs with budget alerts
- [ ] Export usage reports
- [ ] All operations work with local auth
- [ ] All operations work with Keycloak auth

### Non-Functional Requirements

- [ ] Model changes apply in <5 seconds
- [ ] Health dashboard updates every 30s
- [ ] UI remains responsive with 50+ models
- [ ] Module restart doesn't affect backend
- [ ] Works with Docker Compose (100 users)
- [ ] Migration path to Kubernetes defined

### Security Requirements

- [ ] Admin permission required for all operations
- [ ] API keys encrypted at rest
- [ ] No secrets logged or exposed in UI
- [ ] Module communication over HTTPS (prod)
- [ ] Input validation on all commands

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **LiteLLM CLI limitations** | Medium | High | Build custom CLI wrapper; contribute to upstream |
| **Module startup latency** | Low | Medium | Implement connection pooling; add health retries |
| **Redis dependency** | Low | High | Fallback to in-memory registry; add Redis Sentinel |
| **CLI command injection** | Low | Critical | Strict input validation; use parameterized commands |
| **Module version drift** | Medium | Medium | Version compatibility check on registration |
| **Scaling complexity** | Medium | Medium | Clear migration path; start with sidecar pattern |

---

## Future Enhancements

### v1.5 (Post-v1.4)

1. **A/B Testing Framework**
   - Route % of traffic to different models
   - Compare performance metrics
   - Automatic winner selection

2. **Smart Fallbacks**
   - ML-based routing decisions
   - Learn from success patterns
   - Automatic chain optimization

3. **Cost Optimization**
   - Automatic model selection by cost
   - Batch request optimization
   - Usage prediction and budgeting

4. **Additional Modules**
   - Security Scanner module
   - Analytics module
   - Backup/Restore module

### v2.0 (Long-term)

1. **Multi-Region Support**
   - Region-specific model selection
   - Latency-based routing
   - Data residency compliance

2. **Custom Module Marketplace**
   - Third-party modules
   - Module verification system
   - Community contributions

---

## Related Documents

- [Module Development Guide](./module-development-guide.md) *(to be created)*
- [CLI Command Reference](./cli-reference.md) *(to be created)*
- [Migration Guide: Compose to K8s](./migration-guide.md) *(to be created)*

---

**Document Owner:** Architecture Team  
**Reviewers:** Backend Team, Frontend Team, DevOps Team  
**Approved:** Pending Implementation Review
