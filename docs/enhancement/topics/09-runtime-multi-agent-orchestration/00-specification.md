# Runtime Multi-Agent Orchestration - Design Specification

**Topic:** #09 - Runtime Multi-Agent Orchestration (LangGraph Extension)
**Status:** 🔵 DESIGNED
**Target Version:** v1.5
**Date:** 2026-03-15
**Priority:** Medium
**Depends On:** Topic #16 (Multi-Agent Tab Architecture)

---

## Executive Summary

The **Runtime Multi-Agent Orchestration** layer enables AgentOS to coordinate multiple AI agents working together on complex tasks, with each agent running in its own isolated session. This design builds upon Topic #16's multi-agent tab architecture, providing the runtime engine that powers dynamic agent spawning, context isolation, and cross-agent coordination.

### Primary Use Case

**Skill creation workflows** where a parent skill agent spawns child agents to create required dependencies:
- Parent: Skill Builder Agent ("Create email marketing skill")
- Child 1: MCP Builder Agent ("Register SendGrid MCP server")
- Child 2: Tool Builder Agent ("Create personalization tool")

Each child runs in complete context isolation — MCP discussions don't pollute skill intent.

### Key Capabilities

| Capability | Description |
|------------|-------------|
| **Dynamic Session Spawning** | Agents create child sessions at runtime based on task analysis |
| **True Context Isolation** | Each session has independent conversation state, message history, and UI tab |
| **Shared Workspace State** | Parent and children share task-specific context via database |
| **Event-Driven Coordination** | Loosely coupled communication via Redis + PostgreSQL |
| **Lifecycle Management** | Spawn, monitor, pause, resume, complete, and cleanup sessions |
| **Optional Supervisor** | Complex patterns use supervisor agent; simple cases have zero overhead |
| **All Coordination Patterns** | Sequential, parallel-join, fan-out/fan-in, dynamic spawning, supervisor |

### Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Architecture** | Approach B: Session Spawning | True isolation, matches Topic #16, dynamic spawning |
| **Supervisor** | Optional with auto-enable | Zero overhead for simple cases, power when needed |
| **Supervisor Trigger** | Pattern-first, count fallback | `pattern in supervisor_patterns OR len(children) >= min_children` |
| **Event Delivery** | Hybrid Redis + PostgreSQL | Real-time + durability, enterprise-grade |
| **Event Granularity** | Configurable (coarse/medium/fine) | Admin console setting |
| **Error Handling** | 4 strategies per dependency | Retry, notify, alternative, custom |
| **Circuit Breaker** | Disabled by default | Opt-in only; misconfiguration risk |
| **Recursion Depth** | Unlimited (practical limit 3) | Support complex dependency chains |
| **Graph Structure** | DAG-only for v1.5 | No cycles; explicit constraint |

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Architecture Overview](#2-architecture-overview)
3. [Component Design](#3-component-design)
4. [Coordination Patterns](#4-coordination-patterns)
5. [Data Flow](#5-data-flow)
6. [Database Schema](#6-database-schema)
7. [API Specification](#7-api-specification)
8. [Configuration](#8-configuration)
9. [Error Handling](#9-error-handling)
10. [Integration with Topic #16](#10-integration-with-topic-16)
11. [Implementation Phases](#11-implementation-phases)
12. [Testing Strategy](#12-testing-strategy)
13. [Open Questions & Future Work](#13-open-questions--future-work)

---

## 1. Requirements

### 1.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1 | Spawn child agent sessions at runtime | High |
| FR2 | True context isolation (separate message history per agent) | High |
| FR3 | Shared workspace state between parent and children | High |
| FR4 | Event-driven coordination (Redis + PostgreSQL) | High |
| FR5 | Support sequential pipeline pattern | High |
| FR6 | Support parallel-join pattern | High |
| FR7 | Support fan-out/fan-in with partial results | Medium |
| FR8 | Support dynamic spawning pattern | Medium |
| FR9 | Optional supervisor agent for complex patterns | High |
| FR10 | Auto-enable supervisor based on pattern or child count | Medium |
| FR11 | Recursive spawning (parent → child → grandchild) | High |
| FR12 | Configurable event granularity | Medium |
| FR13 | Per-dependency error handling strategies | High |
| FR14 | Lifecycle management (spawn, monitor, complete, cleanup) | High |

### 1.2 Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR1 | Zero overhead for simple cases (no supervisor) | High |
| NFR2 | Graceful degradation if Redis unavailable | High |
| NFR3 | Event durability (survive restarts) | High |
| NFR4 | Horizontal scalability (multiple backend instances) | Medium |
| NFR5 | Backward compatibility with single-agent mode | High |
| NFR6 | Performance: <100ms overhead per spawn | Medium |

### 1.3 Security Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| SR1 | Child sessions inherit parent's user context (JWT) | High |
| SR2 | Workspace state respects RBAC + ACL (same gates as tools) | High |
| SR3 | Audit logging for all spawn/completion events | High |
| SR4 | Child cannot access parent's other children directly | High |
| SR5 | Session isolation enforced at database level | High |

---

## 2. Architecture Overview

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js)                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │                    Multi-Agent Workspace (Topic #16)                  │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │    │
│  │  │ Tab 1: Skill│  │ Tab 2: MCP  │  │ Tab 3: Tool │                  │    │
│  │  │   Agent     │  │   Agent     │  │   Agent     │                  │    │
│  │  │  (Parent)   │  │  (Child)    │  │  (Child)    │                  │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │    │
│  │         │                │                │                          │    │
│  │         └────────────────┴────────────────┘                          │    │
│  │                    CopilotKitProvider (per-tab)                     │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI + LangGraph)                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    MultiAgentOrchestrator                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │   Spawn     │  │  Workspace  │  │   Event     │                  │   │
│  │  │   Service   │  │   Service   │  │   Router    │                  │   │
│  │  │             │  │             │  │             │                  │   │
│  │  │ • Create    │  │ • Shared    │  │ • Redis     │                  │   │
│  │  │   sessions  │  │   state     │  │   pub/sub   │                  │   │
│  │  │ • Manage    │  │ • Context   │  │ • Persist   │                  │   │
│  │  │   lifecycle │  │   passing   │  │   to DB     │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Session Runtime                                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │  LangGraph  │  │  Checkpointer│  │   Agent     │                  │   │
│  │  │   Graph     │  │  (Postgres) │  │   Logic     │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Supervisor Agent (Optional)                       │   │
│  │  • Spawns when pattern in supervisor_patterns OR children >= 3       │   │
│  │  • Manages complex coordination patterns                             │   │
│  │  • Handles error strategies for all children                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE (PostgreSQL) + Redis                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    agent_dependencies (Topic #16)                    │   │
│  │  • parent_session_id, child_session_id, status, context_payload     │   │
│  │  • orchestration_depth, spawn_order, completion_criteria            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    agent_sessions (NEW)                              │   │
│  │  • session_id, parent_session_id, agent_type, workspace_state       │   │
│  │  • depth, status, created_at, completed_at                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    orchestrator_events (NEW)                         │   │
│  │  • event_id, session_id, target_session_id, event_type, payload     │   │
│  │  • created_at, processed_at, processed_by                           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Redis (Celery broker, reused)                     │   │
│  │  • orchestrator:events:{session_id}  (session-specific channel)     │   │
│  │  • orchestrator:broadcast           (broadcast channel)             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Isolation** | Each session has independent checkpointer, message history, and UI tab |
| **Coordination** | Event-driven via Redis + PostgreSQL; no direct agent-to-agent calls |
| **Scalability** | Sessions can run on different backend instances; Redis coordinates |
| **Reliability** | PostgreSQL is source of truth; Redis is optimization |
| **Flexibility** | Optional supervisor; pattern-first activation |
| **Constraints** | DAG-only (no cycles) for v1.5; unlimited depth |

---

## 3. Component Design

### 3.1 Spawn Service

**Responsibility:** Create and manage agent sessions at runtime.

```python
# backend/agents/multi_agent/spawn_service.py

class SpawnService:
    """Service for spawning child agent sessions."""
    
    async def spawn_child(
        self,
        parent_session_id: str,
        agent_type: str,
        context: dict,
        coordination_pattern: Optional[str] = None,
        error_config: Optional[ErrorHandlerConfig] = None,
    ) -> SpawnResult:
        """
        Spawn a child agent session.
        
        Args:
            parent_session_id: ID of the spawning parent session
            agent_type: Type of agent to spawn (skill_builder, mcp_builder, etc.)
            context: Initial context passed to child (purpose, requirements, etc.)
            coordination_pattern: Pattern for coordination (sequential, parallel_join, etc.)
            error_config: Error handling configuration for this dependency
            
        Returns:
            SpawnResult with child_session_id, status, and metadata
        """
        pass
    
    async def spawn_with_supervisor(
        self,
        parent_session_id: str,
        children_configs: list[ChildConfig],
        coordination_pattern: str,
        supervisor_config: Optional[SupervisorConfig] = None,
    ) -> SupervisorSpawnResult:
        """
        Spawn a supervisor that manages multiple children.
        
        Auto-enabled when:
        - coordination_pattern in supervisor_patterns, OR
        - len(children_configs) >= supervisor_min_children
        """
        pass
    
    async def terminate_session(
        self,
        session_id: str,
        reason: str,
        cascade: bool = True,  # Terminate all descendants
    ) -> TerminateResult:
        """Terminate a session and optionally all its descendants."""
        pass
```

**Spawn Algorithm:**

```python
def should_use_supervisor(
    coordination_pattern: Optional[str],
    children_count: int,
    config: MultiAgentConfig,
) -> bool:
    """Determine if supervisor is needed."""
    
    # Pattern-first logic
    if coordination_pattern in config.supervisor_patterns:
        return True
    
    # Count fallback
    if children_count >= config.supervisor_min_children:
        return True
    
    return False
```

### 3.2 Workspace Service

**Responsibility:** Manage shared state between parent and child agents.

```python
# backend/agents/multi_agent/workspace_service.py

class WorkspaceService:
    """Service for shared workspace state management."""
    
    async def update_workspace(
        self,
        session_id: str,
        key: str,
        value: Any,
        propagate_to_children: bool = False,
    ) -> None:
        """
        Update workspace state for a session.
        
        Args:
            session_id: Session to update
            key: Workspace key
            value: Value to store
            propagate_to_children: If True, push to all descendants
        """
        pass
    
    async def get_workspace(
        self,
        session_id: str,
        key: Optional[str] = None,
    ) -> Union[dict, Any]:
        """
        Get workspace state.
        
        Args:
            session_id: Session to read
            key: Specific key, or None for entire workspace
            
        Returns:
            Workspace value or entire workspace dict
        """
        pass
    
    async def inherit_workspace(
        self,
        child_session_id: str,
        parent_session_id: str,
        keys: Optional[list[str]] = None,
    ) -> None:
        """
        Child inherits workspace keys from parent.
        
        Called automatically on spawn. Child gets copy of parent's
        workspace (or specified keys) at spawn time.
        """
        pass
```

**Workspace Data Model:**

```python
# Workspace state stored in agent_sessions.workspace_state (JSONB)

workspace_state = {
    # Core context from parent
    "parent_context": {
        "skill_name": "Email Marketing Skill",
        "skill_description": "Sends personalized email campaigns",
        "required_capabilities": ["send_email", "personalize_template"],
    },
    
    # Child-specific results
    "child_results": {
        "mcp-session-456": {
            "status": "completed",
            "mcp_server_id": "sendgrid-mcp",
            "tools": ["send_email", "get_templates"],
        },
        "tool-session-789": {
            "status": "in_progress",
            "tool_id": None,  # Not yet created
        },
    },
    
    # Shared artifacts
    "artifacts": {
        "requirements_doc": "...",
        "api_spec": "...",
    },
    
    # Metadata
    "created_at": "2026-03-15T10:30:00Z",
    "updated_at": "2026-03-15T10:45:00Z",
}
```

### 3.3 Event Router

**Responsibility:** Route events between sessions via Redis + PostgreSQL.

```python
# backend/agents/multi_agent/event_router.py

class EventRouter:
    """Router for orchestrator events."""
    
    async def publish_event(
        self,
        event: OrchestratorEvent,
        persist: bool = True,  # Always True for durability
    ) -> None:
        """
        Publish an event.
        
        1. Persist to PostgreSQL (orchestrator_events table)
        2. Publish to Redis (for real-time delivery)
        """
        pass
    
    async def subscribe_to_events(
        self,
        session_id: str,
        callback: Callable[[OrchestratorEvent], Awaitable[None]],
        event_types: Optional[list[str]] = None,
    ) -> Subscription:
        """
        Subscribe to events for a session.
        
        Uses Redis pub/sub for real-time delivery.
        Falls back to polling if Redis unavailable.
        """
        pass
    
    async def poll_pending_events(
        self,
        session_id: str,
        since: Optional[datetime] = None,
        event_types: Optional[list[str]] = None,
    ) -> list[OrchestratorEvent]:
        """
        Poll for pending events from PostgreSQL.
        
        Used for:
        - Initial sync on session start
        - Recovery after restart
        - Fallback when Redis unavailable
        """
        pass
```

**Event Types (by Granularity):**

```python
# Coarse granularity (default)
COARSE_EVENTS = [
    "child_spawned",
    "child_status_changed",  # pending → in_progress → completed/failed
    "workspace_updated",
]

# Medium granularity
MEDIUM_EVENTS = COARSE_EVENTS + [
    "child_started",
    "child_checkpoint_saved",
    "child_message_added",
    "workspace_key_updated",
]

# Fine granularity
FINE_EVENTS = MEDIUM_EVENTS + [
    "child_node_entered",
    "child_node_exited",
    "child_tool_called",
    "child_llm_called",
    "event_published",
    "event_processed",
]
```

### 3.4 Supervisor Agent

**Responsibility:** Manage complex coordination patterns and error handling.

```python
# backend/agents/multi_agent/supervisor_agent.py

class SupervisorAgent:
    """
    Supervisor agent for complex multi-agent coordination.
    
    Spawned automatically when:
    - coordination_pattern in supervisor_patterns, OR
    - len(children) >= supervisor_min_children
    """
    
    async def coordinate_parallel_join(
        self,
        children: list[str],
        join_criteria: JoinCriteria,
    ) -> JoinResult:
        """
        Spawn children in parallel, wait for all to complete.
        
        Args:
            children: List of child session IDs to spawn
            join_criteria: Criteria for join (all, any, n_of_m, deadline)
        """
        pass
    
    async def coordinate_fan_out_fan_in(
        self,
        children: list[str],
        deadline_seconds: int,
        min_results: int = 1,
    ) -> FanInResult:
        """
        Scatter to N children, collect by deadline.
        
        Proceeds with partial results if deadline reached.
        """
        pass
    
    async def handle_child_error(
        self,
        child_session_id: str,
        error: Exception,
        error_config: ErrorHandlerConfig,
    ) -> ErrorHandlingResult:
        """
        Handle child error based on configured strategy.
        
        Strategies: retry, notify, alternative, custom
        """
        pass
```

**Supervisor State Machine:**

```
┌─────────┐    spawn children    ┌───────────┐
│  IDLE   │─────────────────────►│ EXECUTING │
└─────────┘                      └─────┬─────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
             ┌──────────┐      ┌──────────┐      ┌──────────┐
             │child_completed│ │child_failed│ │ deadline │
             └────┬─────┘      └────┬─────┘      └────┬─────┘
                  │                  │                  │
                  └──────────────────┼──────────────────┘
                                     │
                                     ▼
                              ┌───────────┐
                              │  JOINING  │
                              │ (wait for │
                              │  criteria)│
                              └─────┬─────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
             ┌──────────┐   ┌──────────┐   ┌──────────┐
             │ COMPLETED│   │  PARTIAL │   │  FAILED  │
             │  (join   │   │ (deadline│   │ (all     │
             │   met)   │   │  reached)│   │  failed) │
             └──────────┘   └──────────┘   └──────────┘
```

---

## 4. Coordination Patterns

### 4.1 Pattern 1: Sequential Pipeline

**Use Case:** Agent A → Agent B → Agent C (assembly line)

**Example:** Skill Builder → MCP Builder → Tool Builder

```python
# Implementation: Direct parent coordination (no supervisor)

async def sequential_pipeline(parent_session_id: str):
    # Step 1: Spawn child A
    child_a = await spawn_service.spawn_child(
        parent_session_id=parent_session_id,
        agent_type="mcp_builder",
        context={"purpose": "Register email MCP"},
    )
    
    # Step 2: Wait for completion
    await wait_for_child(child_a.session_id)
    
    # Step 3: Spawn child B with results from A
    mcp_result = await workspace_service.get_workspace(
        child_a.session_id, "result"
    )
    
    child_b = await spawn_service.spawn_child(
        parent_session_id=parent_session_id,
        agent_type="tool_builder",
        context={
            "purpose": "Create email tool",
            "mcp_tools": mcp_result["tools"],
        },
    )
    
    # Step 4: Wait for completion
    await wait_for_child(child_b.session_id)
    
    # Step 5: Continue with parent logic
    return {"child_a": child_a.session_id, "child_b": child_b.session_id}
```

**Supervisor Needed?** No (sequential, 2 children)

### 4.2 Pattern 2: Parallel with Join

**Use Case:** Spawn A, B, C in parallel → wait for all → synthesize

**Example:** Query 3 knowledge sources, merge results

```python
# Implementation: With supervisor (parallel pattern)

async def parallel_with_join(parent_session_id: str):
    children_configs = [
        ChildConfig(agent_type="research_agent", context={"source": "docs"}),
        ChildConfig(agent_type="research_agent", context={"source": "database"}),
        ChildConfig(agent_type="research_agent", context={"source": "api"}),
    ]
    
    # Supervisor auto-enabled: parallel pattern + 3 children
    result = await spawn_service.spawn_with_supervisor(
        parent_session_id=parent_session_id,
        children_configs=children_configs,
        coordination_pattern="parallel_join",
        supervisor_config=SupervisorConfig(
            join_criteria=JoinCriteria.ALL_COMPLETED,
            error_strategy=ErrorStrategy.RETRY,
        ),
    )
    
    # Results synthesized by supervisor
    return result.synthesized_output
```

**Supervisor Needed?** Yes (parallel pattern in supervisor_patterns)

### 4.3 Pattern 3: Fan-Out/Fan-In with Partial Results

**Use Case:** Scatter to N children → collect by deadline → proceed with partial

**Example:** Query 5 sources, use whatever returns in 10s

```python
# Implementation: With supervisor

async def fan_out_fan_in_partial(parent_session_id: str):
    children_configs = [
        ChildConfig(agent_type="search_agent", context={"engine": "google"}),
        ChildConfig(agent_type="search_agent", context={"engine": "bing"}),
        ChildConfig(agent_type="search_agent", context={"engine": "duckduckgo"}),
        ChildConfig(agent_type="search_agent", context={"engine": "brave"}),
        ChildConfig(agent_type="search_agent", context={"engine": "wolfram"}),
    ]
    
    result = await spawn_service.spawn_with_supervisor(
        parent_session_id=parent_session_id,
        children_configs=children_configs,
        coordination_pattern="fan_out_fan_in",
        supervisor_config=SupervisorConfig(
            deadline_seconds=10,
            min_results=2,  # Proceed with at least 2 results
            max_results=5,  # Cap at 5
        ),
    )
    
    # result.completed: Children that finished by deadline
    # result.partial: True if deadline reached before all completed
    return result
```

**Supervisor Needed?** Yes (complex deadline logic)

### 4.4 Pattern 4: Dynamic Spawning

**Use Case:** Analyze task → spawn optimal children at runtime

**Example:** Skill creation → analyze requirements → spawn needed builders

```python
# Implementation: With supervisor (dynamic pattern)

async def dynamic_spawning(parent_session_id: str):
    # Phase 1: Analysis (single agent)
    analysis = await run_analysis_agent(
        "Create email marketing skill with personalization"
    )
    
    # Phase 2: Dynamic child spawning based on analysis
    children_configs = []
    
    if analysis.needs_mcp:
        children_configs.append(
            ChildConfig(agent_type="mcp_builder", context=analysis.mcp_context)
        )
    
    if analysis.needs_tools:
        for tool in analysis.required_tools:
            children_configs.append(
                ChildConfig(agent_type="tool_builder", context=tool)
            )
    
    if analysis.needs_agents:
        for agent in analysis.required_agents:
            children_configs.append(
                ChildConfig(agent_type="agent_builder", context=agent)
            )
    
    # Phase 3: Coordinate all spawned children
    if children_configs:
        result = await spawn_service.spawn_with_supervisor(
            parent_session_id=parent_session_id,
            children_configs=children_configs,
            coordination_pattern="dynamic",
            supervisor_config=SupervisorConfig(
                dynamic_ordering=True,  # Children may have dependencies
                error_strategy=ErrorStrategy.NOTIFY_AND_WAIT,
            ),
        )
        return result
```

**Supervisor Needed?** Yes (dynamic pattern in supervisor_patterns)

### 4.5 Pattern 5: Hierarchical Delegation

**Use Case:** Master decomposes task → delegates to specialists → synthesizes

**Example:** Email task → delegate to Email Agent → return result

```python
# Implementation: Direct (already works in current AgentOS)

async def hierarchical_delegation(parent_session_id: str):
    # This is the existing master_agent routing pattern
    # Extended to use session spawning for isolation
    
    child = await spawn_service.spawn_child(
        parent_session_id=parent_session_id,
        agent_type="email_agent",
        context={"task": "Send meeting reminder"},
    )
    
    # Wait and return (existing pattern)
    result = await wait_for_child(child.session_id)
    return result
```

**Supervisor Needed?** No (single child, simple delegation)

### 4.6 Pattern Support Matrix

| Pattern | Children | Supervisor | Use Case |
|---------|----------|------------|----------|
| Sequential Pipeline | 2+ | No | Assembly line workflows |
| Parallel with Join | 2+ | Yes | Query multiple sources, merge all |
| Fan-Out/Fan-In (Partial) | 3+ | Yes | Deadline-based collection |
| Dynamic Spawning | Variable | Yes | Runtime analysis decides |
| Hierarchical Delegation | 1 | No | Simple task routing |

---

## 5. Data Flow

### 5.1 Complete Skill Creation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLOW: Creating "Email Marketing Skill"                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER: "I need a skill that sends personalized email campaigns"               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: Parent analyzes requirements                                │   │
│  │  Agent: Skill Builder (Session: skill-001)                           │   │
│  │  Action: Detects missing dependencies                                │   │
│  │  Result: Needs MCP + Tool                                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: Determine supervisor need                                   │   │
│  │  Pattern: "parallel_join" (in supervisor_patterns)                   │   │
│  │  Children: 2                                                         │   │
│  │  Decision: Use supervisor (pattern match)                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: Spawn supervisor                                            │   │
│  │  Action: spawn_with_supervisor()                                     │   │
│  │  Result: Supervisor session created (supervisor-001)                 │   │
│  │  DB: agent_dependencies row created                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: Supervisor spawns children                                  │   │
│  │                                                                      │   │
│  │  Child 1: MCP Builder (mcp-001)                                      │   │
│  │  • Inherits workspace from parent                                    │   │
│  │  • Context: {"purpose": "SendGrid integration"}                      │   │
│  │  • UI: New tab opens                                                 │   │
│  │                                                                      │   │
│  │  Child 2: Tool Builder (tool-001)                                    │   │
│  │  • Inherits workspace from parent                                    │   │
│  │  • Context: {"purpose": "Personalization logic"}                     │   │
│  │  • UI: New tab opens                                                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 5: Children execute independently                              │   │
│  │                                                                      │   │
│  │  MCP Builder (Tab 2):                                                │   │
│  │  • User: "Use SendGrid, authenticate with API key"                   │   │
│  │  • Agent: Guides through MCP registration                            │   │
│  │  • Progress: workspace updated with intermediate results             │   │
│  │                                                                      │   │
│  │  Tool Builder (Tab 3):                                               │   │
│  │  • User: "Fetch from CRM, merge into template"                       │   │
│  │  • Agent: Generates Python code                                      │   │
│  │  • Progress: workspace updated with code drafts                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 6: Events flow to supervisor                                   │   │
│  │                                                                      │   │
│  │  Redis: orchestrator:events:supervisor-001                           │   │
│  │  • Event: {type: "child_status_changed", child: "mcp-001",           │   │
│  │            status: "in_progress"}                                    │   │
│  │  • Event: {type: "child_status_changed", child: "tool-001",          │   │
│  │            status: "in_progress"}                                    │   │
│  │                                                                      │   │
│  │  DB: orchestrator_events persisted for audit                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 7: Child 1 completes                                           │   │
│  │                                                                      │   │
│  │  MCP Builder:                                                        │   │
│  │  • Result: MCP server registered (sendgrid-mcp)                      │   │
│  │  • Workspace: result_payload updated                                 │   │
│  │  • Event: child_completed → supervisor                               │   │
│  │                                                                      │   │
│  │  UI: Tab 2 shows ✅ completed                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 8: Supervisor applies join criteria                            │   │
│  │                                                                      │   │
│  │  Check: JoinCriteria.ALL_COMPLETED                                   │   │
│  │  Status: 1/2 completed (waiting for tool-001)                        │   │
│  │  Action: Continue monitoring                                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 9: Child 2 completes                                           │   │
│  │                                                                      │   │
│  │  Tool Builder:                                                       │   │
│  │  • Result: Tool registered (personalize-template)                    │   │
│  │  • Event: child_completed → supervisor                               │   │
│  │                                                                      │   │
│  │  UI: Tab 3 shows ✅ completed                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 10: Join criteria met                                          │   │
│  │                                                                      │   │
│  │  Supervisor:                                                         │   │
│  │  • All children completed                                            │   │
│  │  • Synthesize results                                                │   │
│  │  • Update parent workspace                                           │   │
│  │  • Event: coordination_completed → parent                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 11: Parent resumes                                             │   │
│  │                                                                      │   │
│  │  Skill Builder (Tab 1):                                              │   │
│  │  • Receives coordination_completed event                             │   │
│  │  • Reads workspace: both dependencies ready                          │   │
│  │  • Message: "Great! SendGrid MCP and personalization tool are        │   │
│  │             ready. Now let's build the skill workflow..."            │   │
│  │                                                                      │   │
│  │  UI: All tabs show ✅, parent tab active                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Error Handling Flow (Retry Strategy)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLOW: Child Failure with Retry                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Child: MCP Builder (mcp-001)                                                │
│  Event: child_failed (API authentication error)                              │
│  Config: ErrorStrategy.RETRY, max_attempts=3, backoff=exponential            │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: Supervisor receives failure event                           │   │
│  │  Event: {type: "child_failed", child: "mcp-001", error: {...}}       │   │
│  │  Current attempt: 1/3                                                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: Apply retry strategy                                        │   │
│  │  Backoff: 1000ms * 2^1 = 2000ms                                      │   │
│  │  Action: Schedule retry after delay                                  │   │
│  │  UI: Tab 2 shows "⚠️ Retrying (1/3)"                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: Retry executed                                              │   │
│  │  Action: Reset child session, preserve workspace                     │   │
│  │  Result: Child restarts from last checkpoint                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: Max attempts exceeded                                       │   │
│  │  After 3 failed attempts...                                          │   │
│  │  Decision: Escalate to error_config.fallback or notify               │   │
│  │                                                                      │   │
│  │  Option A: Spawn alternative (if configured)                         │   │
│  │  • Alternative: Use AWS SES instead of SendGrid                      │   │
│  │                                                                      │   │
│  │  Option B: Notify and wait (if configured)                           │   │
│  │  • Pause supervisor                                                  │   │
│  │  • Notify user in parent tab                                         │   │
│  │  • Wait for manual intervention                                      │   │
│  │                                                                      │   │
│  │  Option C: Fail coordination (default)                               │   │
│  │  • Mark coordination as failed                                       │   │
│  │  • Notify parent                                                     │   │
│  │  • User decides next steps                                           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Database Schema

### 6.1 Extended agent_dependencies Table

```sql
-- Migration: 032_extend_agent_dependencies_for_orchestration.sql

-- Add orchestration columns to existing table
ALTER TABLE agent_dependencies
    ADD COLUMN IF NOT EXISTS orchestration_depth INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS spawn_order INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS completion_criteria JSONB,
    ADD COLUMN IF NOT EXISTS error_config JSONB,
    ADD COLUMN IF NOT EXISTS coordination_pattern VARCHAR;

-- Add index for depth-based queries
CREATE INDEX IF NOT EXISTS idx_agent_deps_depth 
    ON agent_dependencies(orchestration_depth);

COMMENT ON COLUMN agent_dependencies.orchestration_depth IS 
    'Nesting level: 0=direct child, 1=grandchild, etc.';
COMMENT ON COLUMN agent_dependencies.completion_criteria IS 
    'JSON defining when this dependency is considered complete';
COMMENT ON COLUMN agent_dependencies.error_config IS 
    'Error handling configuration for this dependency';
```

### 6.2 New agent_sessions Table

```sql
-- Migration: 033_create_agent_sessions.sql

CREATE TABLE agent_sessions (
    session_id VARCHAR PRIMARY KEY,
    parent_session_id VARCHAR REFERENCES agent_sessions(session_id),
    user_id UUID NOT NULL,
    agent_type VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'active',
    
    -- Workspace state (shared context)
    workspace_state JSONB DEFAULT '{}',
    
    -- Orchestration metadata
    depth INT DEFAULT 0,
    is_supervisor BOOLEAN DEFAULT FALSE,
    coordination_pattern VARCHAR,
    
    -- Configuration references
    error_config_id UUID,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT valid_status CHECK (status IN (
        'active', 'paused', 'completed', 'failed', 'cancelled'
    )),
    CONSTRAINT valid_depth CHECK (depth >= 0)
);

-- Indexes
CREATE INDEX idx_agent_sessions_parent 
    ON agent_sessions(parent_session_id, status);
CREATE INDEX idx_agent_sessions_user 
    ON agent_sessions(user_id, created_at);
CREATE INDEX idx_agent_sessions_status 
    ON agent_sessions(status, updated_at);
CREATE INDEX idx_agent_sessions_workspace 
    ON agent_sessions USING GIN (workspace_state);

COMMENT ON TABLE agent_sessions IS 
    'Registry of all multi-agent orchestration sessions';
```

### 6.3 New orchestrator_events Table

```sql
-- Migration: 034_create_orchestrator_events.sql

CREATE TABLE orchestrator_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event routing
    session_id VARCHAR NOT NULL,
    target_session_id VARCHAR,  -- NULL = broadcast
    
    -- Event content
    event_type VARCHAR NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    
    -- Granularity tracking
    granularity VARCHAR NOT NULL DEFAULT 'medium',
    
    -- Processing state
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    processed_by VARCHAR,  -- session_id that processed
    
    -- TTL for cleanup (optional)
    expires_at TIMESTAMP WITH TIME ZONE 
        DEFAULT NOW() + INTERVAL '7 days'
);

-- Indexes
CREATE INDEX idx_orchestrator_events_target 
    ON orchestrator_events(target_session_id, processed_at, created_at);
CREATE INDEX idx_orchestrator_events_session 
    ON orchestrator_events(session_id, created_at DESC);
CREATE INDEX idx_orchestrator_events_type 
    ON orchestrator_events(event_type, created_at);
CREATE INDEX idx_orchestrator_events_unprocessed 
    ON orchestrator_events(processed_at) 
    WHERE processed_at IS NULL;

-- Partition by time for scale (optional, for v1.5+)
-- CREATE TABLE orchestrator_events_partitioned (...) PARTITION BY RANGE (created_at);

COMMENT ON TABLE orchestrator_events IS 
    'Event log for multi-agent orchestration. Source of truth for event history.';
```

### 6.4 New orchestrator_config Table

```sql
-- Migration: 035_create_orchestrator_config.sql

CREATE TABLE orchestrator_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event granularity
    event_granularity VARCHAR NOT NULL DEFAULT 'medium',
    
    -- Supervisor auto-enable
    supervisor_auto_enable BOOLEAN DEFAULT TRUE,
    supervisor_min_children INT DEFAULT 3,
    supervisor_patterns TEXT[] DEFAULT ARRAY['parallel_join', 'fan_out_fan_in', 'dynamic'],
    
    -- Retry configuration
    default_max_retries INT DEFAULT 3,
    default_backoff_strategy VARCHAR DEFAULT 'exponential',
    default_backoff_ms INT DEFAULT 1000,
    
    -- Resource limits
    max_concurrent_children INT DEFAULT 10,
    max_depth INT DEFAULT 3,
    default_timeout_seconds INT DEFAULT 300,
    
    -- Circuit breaker (disabled by default for v1.5)
    circuit_breaker_enabled BOOLEAN DEFAULT FALSE,
    circuit_breaker_threshold INT DEFAULT 5,
    circuit_breaker_timeout_ms INT DEFAULT 30000,
    
    -- Audit
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by UUID
);

-- Single row config
INSERT INTO orchestrator_config (id) VALUES (gen_random_uuid());

COMMENT ON TABLE orchestrator_config IS 
    'System-wide multi-agent orchestration configuration';
```

### 6.5 Entity Relationship Diagram

```
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  agent_sessions  │       │ agent_dependencies│       │orchestrator_events│
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ PK session_id    │◄──────┤ FK parent_session_id      │ FK session_id    │
│ FK parent_session_id────►│ FK child_session_id       │ target_session_id│
│    (self-ref)    │       │ status           │       │ event_type       │
│ user_id          │       │ context_payload  │       │ payload          │
│ agent_type       │       │ orchestration_depth│     │ processed_at     │
│ status           │       │ error_config     │       └──────────────────┘
│ workspace_state  │       │ coordination_pattern      │
│ depth            │       └──────────────────┘       ┌──────────────────┐
│ is_supervisor    │                                  │orchestrator_config│
└──────────────────┘                                  ├──────────────────┤
                                                      │ event_granularity│
                                                      │ supervisor_*     │
                                                      │ retry_*          │
                                                      │ max_*            │
                                                      │ circuit_breaker_*│
                                                      └──────────────────┘
```

---

## 7. API Specification

### 7.1 Spawn Endpoints

```python
# POST /api/multi-agent/sessions/{session_id}/spawn
# Spawn a single child session (direct coordination)

class SpawnChildRequest(BaseModel):
    agent_type: str  # skill_builder, mcp_builder, tool_builder, etc.
    context: dict    # Initial context for child
    coordination_pattern: Optional[str] = None  # For pattern tracking
    error_config: Optional[ErrorHandlerConfig] = None

class SpawnChildResponse(BaseModel):
    child_session_id: str
    parent_session_id: str
    status: str  # spawned
    created_at: datetime
    ui_tab_url: str  # Frontend URL for new tab

# POST /api/multi-agent/sessions/{session_id}/spawn-supervised
# Spawn multiple children with supervisor

class SpawnSupervisedRequest(BaseModel):
    children: list[ChildConfig]
    coordination_pattern: str
    supervisor_config: Optional[SupervisorConfig] = None
    error_config: Optional[ErrorHandlerConfig] = None

class SpawnSupervisedResponse(BaseModel):
    supervisor_session_id: str
    parent_session_id: str
    children: list[ChildSpawnInfo]
    status: str  # coordinating
```

### 7.2 Workspace Endpoints

```python
# GET /api/multi-agent/sessions/{session_id}/workspace
# Get workspace state

class GetWorkspaceResponse(BaseModel):
    session_id: str
    workspace_state: dict
    inherited_from: Optional[str]  # Parent session_id if inherited

# PATCH /api/multi-agent/sessions/{session_id}/workspace
# Update workspace state

class UpdateWorkspaceRequest(BaseModel):
    updates: dict  # Key-value pairs to update
    propagate_to_children: bool = False

class UpdateWorkspaceResponse(BaseModel):
    session_id: str
    updated_keys: list[str]
    propagated_to: list[str]  # Child session_ids if propagated
```

### 7.3 Event Endpoints

```python
# GET /api/multi-agent/sessions/{session_id}/events
# Poll events for a session

class PollEventsRequest(BaseModel):
    since: Optional[datetime] = None
    event_types: Optional[list[str]] = None
    granularity: Optional[str] = None  # Override system default

class PollEventsResponse(BaseModel):
    session_id: str
    events: list[OrchestratorEvent]
    has_more: bool  # Pagination

# WebSocket /ws/multi-agent/events/{session_id}
# Real-time event streaming (optional, for v1.5+)
```

### 7.4 Lifecycle Endpoints

```python
# POST /api/multi-agent/sessions/{session_id}/pause
# Pause a session (and optionally all descendants)

class PauseRequest(BaseModel):
    cascade: bool = True  # Pause all descendants
    reason: Optional[str] = None

# POST /api/multi-agent/sessions/{session_id}/resume
# Resume a paused session

class ResumeRequest(BaseModel):
    cascade: bool = True  # Resume all descendants

# POST /api/multi-agent/sessions/{session_id}/terminate
# Terminate a session

class TerminateRequest(BaseModel):
    cascade: bool = True  # Terminate all descendants
    reason: str
```

### 7.5 Configuration Endpoints

```python
# GET /api/admin/multi-agent/config
# Get orchestrator configuration

class GetConfigResponse(BaseModel):
    event_granularity: str
    supervisor_auto_enable: bool
    supervisor_min_children: int
    supervisor_patterns: list[str]
    default_error_strategy: str
    retry_config: RetryConfig
    max_concurrent_children: int
    max_depth: int
    circuit_breaker_enabled: bool

# PUT /api/admin/multi-agent/config
# Update orchestrator configuration (admin only)

class UpdateConfigRequest(BaseModel):
    event_granularity: Optional[str] = None
    supervisor_auto_enable: Optional[bool] = None
    supervisor_min_children: Optional[int] = None
    # ... etc
```

---

## 8. Configuration

### 8.1 System Configuration (Admin Console)

```typescript
// Frontend: Admin Console Settings Page
// Route: /admin/settings/multi-agent

interface MultiAgentConfig {
  // Event granularity
  eventGranularity: 'coarse' | 'medium' | 'fine';
  
  // Supervisor configuration
  supervisorAutoEnable: boolean;
  supervisorMinChildren: number;
  supervisorPatterns: string[];
  
  // Default retry configuration
  defaultMaxRetries: number;
  defaultBackoffStrategy: 'fixed' | 'linear' | 'exponential';
  defaultBackoffMs: number;
  
  // Resource limits
  maxConcurrentChildren: number;
  maxDepth: number;
  defaultTimeoutSeconds: number;
  
  // Circuit breaker (disabled by default)
  circuitBreakerEnabled: boolean;
  circuitBreakerThreshold: number;
  circuitBreakerTimeoutMs: number;
}

// Default configuration for v1.5
const DEFAULT_CONFIG: MultiAgentConfig = {
  eventGranularity: 'medium',
  supervisorAutoEnable: true,
  supervisorMinChildren: 3,
  supervisorPatterns: [
    'parallel_join',
    'fan_out_fan_in', 
    'dynamic'
  ],
  defaultMaxRetries: 3,
  defaultBackoffStrategy: 'exponential',
  defaultBackoffMs: 1000,
  maxConcurrentChildren: 10,
  maxDepth: 3,
  defaultTimeoutSeconds: 300,
  circuitBreakerEnabled: false,  // Disabled by default
  circuitBreakerThreshold: 5,
  circuitBreakerTimeoutMs: 30000,
};
```

### 8.2 Per-Dependency Error Configuration

```python
# Error handling can be configured per dependency

class ErrorHandlerConfig(BaseModel):
    strategy: ErrorStrategy = ErrorStrategy.RETRY
    
    # Retry configuration
    max_retries: int = 3
    retry_backoff_strategy: str = 'exponential'  # fixed, linear, exponential
    retry_backoff_ms: int = 1000
    
    # Alternative agent (for SPAWN_ALTERNATIVE strategy)
    alternative_agent_type: Optional[str] = None
    alternative_context: Optional[dict] = None
    
    # Custom handler (for CUSTOM strategy)
    custom_handler_code: Optional[str] = None  # Python code
    
    # Notification channels (for NOTIFY_AND_WAIT strategy)
    notify_channels: list[str] = ['ui', 'email']  # ui, email, slack, etc.
    
    # Circuit breaker (disabled by default)
    circuit_breaker_enabled: bool = False
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_ms: int = 30000
```

### 8.3 Configuration UI Mockup

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Multi-Agent Orchestration Settings                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Event Granularity ──────────────────────────────────────────────────┐   │
│  │  ○ Coarse (status changes only)                                       │   │
│  │  ● Medium (status + checkpoint + messages)           [Recommended]    │   │
│  │  ○ Fine (all events including tool calls)                             │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Supervisor Agent ───────────────────────────────────────────────────┐   │
│  │  ☑ Auto-enable supervisor for complex patterns                       │   │
│  │     Minimum children to trigger: [3]                                 │   │
│  │     Auto-enable patterns: ☑ parallel_join ☑ fan_out_fan_in ☑ dynamic│   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Default Retry Configuration ────────────────────────────────────────┐   │
│  │  Max retries: [3]                                                    │   │
│  │  Backoff strategy: [Exponential ▼]                                   │   │
│  │  Backoff base (ms): [1000]                                           │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Resource Limits ────────────────────────────────────────────────────┐   │
│  │  Max concurrent children: [10]                                       │   │
│  │  Max nesting depth: [3]                                              │   │
│  │  Default timeout (seconds): [300]                                    │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Circuit Breaker ────────────────────────────────────────────────────┐   │
│  │  ☐ Enable circuit breaker  [⚠️ Advanced: Requires careful tuning]     │   │
│  │     Failure threshold: [5]          Timeout (ms): [30000]             │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│                                    [Save Changes]                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Error Handling

### 9.1 Error Handling Strategies

| Strategy | When to Use | Behavior |
|----------|-------------|----------|
| **RETRY** | Transient failures (network, rate limits) | Auto-retry with backoff, max attempts |
| **NOTIFY_AND_WAIT** | Requires human decision | Pause, notify user, wait for input |
| **SPAWN_ALTERNATIVE** | Fallback available | Retry with different approach/agent |
| **CUSTOM** | Complex logic needed | Execute custom Python handler |

### 9.2 Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Error Handling Decision Tree                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Child Failure Detected                                                      │
│         │                                                                    │
│         ▼                                                                    │
│  ┌───────────────┐                                                           │
│  │ Check Config  │                                                           │
│  │ error_config  │                                                           │
│  │ .strategy     │                                                           │
│  └───────┬───────┘                                                           │
│          │                                                                   │
│    ┌─────┼─────┬─────────┬─────────┐                                         │
│    ▼     ▼     ▼         ▼         ▼                                         │
│ ┌────┐┌────┐┌────┐  ┌────────┐ ┌──────┐                                     │
│ │RETRY││NOTIFY││ALT │  │ CUSTOM  │ │ DEFAULT│                                    │
│ └─┬──┘└─┬──┘└─┬──┘  └────┬───┘ └──┬───┘                                     │
│   │     │     │          │        │                                         │
│   ▼     ▼     ▼          ▼        ▼                                         │
│  Retry Notify Spawn    Execute  Apply                                       │
│  with   user   alternative custom system                                    │
│  backoff       agent     handler  default                                   │
│  (max 3)       (config)  (Python) (RETRY)                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Retry with Exponential Backoff

```python
# Algorithm

def calculate_backoff_delay(
    attempt: int,
    base_ms: int,
    strategy: str,
) -> int:
    """Calculate delay before retry."""
    
    if strategy == 'fixed':
        return base_ms
    elif strategy == 'linear':
        return base_ms * attempt
    elif strategy == 'exponential':
        return base_ms * (2 ** (attempt - 1))
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

# Examples (base_ms = 1000)
# Attempt 1: 1000ms (exponential: 1000 * 2^0 = 1000)
# Attempt 2: 2000ms (exponential: 1000 * 2^1 = 2000)
# Attempt 3: 4000ms (exponential: 1000 * 2^2 = 4000)
```

### 9.4 Circuit Breaker (Disabled by Default)

```python
# Circuit breaker state machine

class CircuitBreaker:
    """
    Circuit breaker pattern for fault tolerance.
    
    ⚠️ Disabled by default in v1.5. Enable only after careful tuning.
    """
    
    def __init__(self, threshold: int, timeout_ms: int):
        self.threshold = threshold  # Failures before opening
        self.timeout_ms = timeout_ms  # Time before half-open
        self.failure_count = 0
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = None
    
    def record_success(self):
        """Record successful call."""
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.threshold:
            self.state = 'OPEN'
    
    def can_execute(self) -> bool:
        """Check if call should proceed."""
        if self.state == 'CLOSED':
            return True
        elif self.state == 'OPEN':
            # Check if timeout elapsed
            elapsed = (time.time() - self.last_failure_time) * 1000
            if elapsed >= self.timeout_ms:
                self.state = 'HALF_OPEN'
                return True
            return False
        elif self.state == 'HALF_OPEN':
            return True
```

---

## 10. Integration with Topic #16

### 10.1 Topic #16 Recap

Topic #16 (Multi-Agent Tab Architecture) provides:
- **Tab-based UI** for multiple agents
- **Database schema** (`agent_dependencies` table)
- **Frontend components** (`MultiAgentWizard`, `TabManager`)
- **Context isolation** via separate CopilotKit instances

### 10.2 Integration Points

| Topic #16 Component | Topic #9 Integration | Purpose |
|---------------------|----------------------|---------|
| `agent_dependencies` table | Extended with orchestration columns | Track parent-child + coordination metadata |
| `TabManager` hook | Spawn new tabs via `spawn_child()` | UI for each child session |
| `DependencyNotifier` | Poll orchestrator events | Real-time status updates |
| `MultiAgentWizard` | Mount supervisor agent when needed | Complex coordination UI |

### 10.3 Frontend Integration Code

```typescript
// frontend/src/hooks/use-multi-agent-spawn.ts

import { useCallback } from 'react';
import { useAgentTabs } from './use-agent-tabs';
import { useEventPolling } from './use-event-polling';

interface UseMultiAgentSpawnOptions {
  parentSessionId: string;
  onChildSpawned?: (childSessionId: string) => void;
  onChildCompleted?: (childSessionId: string, result: any) => void;
}

export function useMultiAgentSpawn(options: UseMultiAgentSpawnOptions) {
  const { addTab } = useAgentTabs();
  const { startPolling } = useEventPolling();
  
  const spawnChild = useCallback(async (config: ChildConfig) => {
    // 1. Call API to spawn child
    const response = await fetch(
      `/api/multi-agent/sessions/${options.parentSessionId}/spawn`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      }
    );
    
    const data = await response.json();
    
    // 2. Open new tab for child
    addTab({
      id: data.child_session_id,
      title: `${config.agent_type} Agent`,
      type: 'agent',
      sessionId: data.child_session_id,
      parentSessionId: options.parentSessionId,
      status: 'active',
    });
    
    // 3. Start polling for events
    startPolling(data.child_session_id, (event) => {
      if (event.type === 'child_completed') {
        options.onChildCompleted?.(data.child_session_id, event.payload);
      }
    });
    
    // 4. Callback
    options.onChildSpawned?.(data.child_session_id);
    
    return data.child_session_id;
  }, [options.parentSessionId, addTab, startPolling]);
  
  const spawnSupervised = useCallback(async (request: SpawnSupervisedRequest) => {
    // Similar to spawnChild, but handles supervisor session
    // and multiple children
    const response = await fetch(
      `/api/multi-agent/sessions/${options.parentSessionId}/spawn-supervised`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      }
    );
    
    const data = await response.json();
    
    // Open tabs for supervisor + all children
    addTab({
      id: data.supervisor_session_id,
      title: 'Coordinator',
      type: 'supervisor',
      sessionId: data.supervisor_session_id,
      isSupervisor: true,
    });
    
    for (const child of data.children) {
      addTab({
        id: child.session_id,
        title: `${child.agent_type} Agent`,
        type: 'agent',
        sessionId: child.session_id,
        parentSessionId: data.supervisor_session_id,
      });
    }
    
    return data;
  }, [options.parentSessionId, addTab]);
  
  return { spawnChild, spawnSupervised };
}
```

---

## 11. Implementation Phases

### Phase 1: Core Infrastructure (Weeks 1-2)

**Goal:** Database schema, basic services, simple sequential pattern

**Tasks:**
- [ ] Migration: Extend `agent_dependencies` table
- [ ] Migration: Create `agent_sessions` table
- [ ] Migration: Create `orchestrator_events` table
- [ ] Migration: Create `orchestrator_config` table
- [ ] Implement SpawnService (basic spawn only)
- [ ] Implement WorkspaceService
- [ ] Implement EventRouter (PostgreSQL only, no Redis)
- [ ] API endpoints: spawn, workspace read/write
- [ ] Tests: Unit tests for services

**Deliverable:** Can spawn single child, basic workspace sharing

### Phase 2: Event System & Coordination (Weeks 3-4)

**Goal:** Redis integration, event routing, sequential pattern

**Tasks:**
- [ ] Redis integration for real-time events
- [ ] EventRouter: Redis pub/sub + PostgreSQL fallback
- [ ] Implement sequential pipeline pattern
- [ ] Frontend: useMultiAgentSpawn hook
- [ ] Frontend: Event polling for status updates
- [ ] Integration with Topic #16 TabManager
- [ ] Tests: Integration tests for event flow

**Deliverable:** Sequential pipelines work end-to-end

### Phase 3: Supervisor Agent (Weeks 5-6)

**Goal:** Optional supervisor, complex patterns

**Tasks:**
- [ ] Implement SupervisorAgent class
- [ ] Implement parallel_join pattern
- [ ] Implement fan_out_fan_in pattern
- [ ] Auto-enable logic (pattern-first, count fallback)
- [ ] API endpoints: spawn-supervised, coordination status
- [ ] Frontend: Supervisor tab UI
- [ ] Tests: Multi-child coordination tests

**Deliverable:** Complex patterns work with supervisor

### Phase 4: Error Handling (Weeks 7-8)

**Goal:** Robust error handling, retry, recovery

**Tasks:**
- [ ] Implement ErrorHandler with 4 strategies
- [ ] Retry with exponential backoff
- [ ] Alternative agent spawning
- [ ] NOTIFY_AND_WAIT with UI integration
- [ ] Error configuration UI (Admin Console)
- [ ] Tests: Error injection and recovery tests

**Deliverable:** Graceful handling of child failures

### Phase 5: Dynamic Spawning & Polish (Weeks 9-10)

**Goal:** Dynamic patterns, system configuration, polish

**Tasks:**
- [ ] Implement dynamic spawning pattern
- [ ] Admin Console: Multi-agent configuration panel
- [ ] Configurable event granularity
- [ ] Resource limits enforcement
- [ ] Performance optimization
- [ ] Documentation and examples
- [ ] E2E tests: Full skill creation workflow

**Deliverable:** Production-ready multi-agent orchestration

### Timeline Summary

| Phase | Duration | Key Deliverable |
|-------|----------|-----------------|
| Phase 1 | Weeks 1-2 | Core infrastructure, simple spawn |
| Phase 2 | Weeks 3-4 | Event system, sequential pattern |
| Phase 3 | Weeks 5-6 | Supervisor, complex patterns |
| Phase 4 | Weeks 7-8 | Error handling, retry |
| Phase 5 | Weeks 9-10 | Dynamic spawning, polish |
| **Total** | **10 weeks** | **Production-ready** |

---

## 12. Testing Strategy

### 12.1 Unit Tests

```python
# backend/tests/multi_agent/test_spawn_service.py

async def test_spawn_creates_session():
    """Test that spawn creates a valid session."""
    service = SpawnService()
    
    result = await service.spawn_child(
        parent_session_id="parent-001",
        agent_type="mcp_builder",
        context={"purpose": "test"},
    )
    
    assert result.child_session_id is not None
    assert result.parent_session_id == "parent-001"
    
    # Verify database state
    session = await get_session(result.child_session_id)
    assert session.agent_type == "mcp_builder"
    assert session.depth == 1  # Direct child

async def test_workspace_inheritance():
    """Test that children inherit workspace from parent."""
    # Set up parent workspace
    await workspace_service.update_workspace(
        "parent-001", "key1", "value1"
    )
    
    # Spawn child
    result = await spawn_service.spawn_child(
        parent_session_id="parent-001",
        agent_type="tool_builder",
        context={},
    )
    
    # Verify inheritance
    workspace = await workspace_service.get_workspace(
        result.child_session_id
    )
    assert workspace["key1"] == "value1"
```

### 12.2 Integration Tests

```python
# backend/tests/multi_agent/test_coordination_patterns.py

async def test_sequential_pipeline():
    """Test sequential pipeline pattern."""
    parent_id = "parent-seq"
    
    # Spawn first child
    child_a = await spawn_service.spawn_child(
        parent_id, "agent_a", {"step": 1}
    )
    
    # Simulate completion
    await simulate_child_completion(child_a.session_id, {"result": "A"})
    
    # Spawn second child (depends on first)
    child_b = await spawn_service.spawn_child(
        parent_id, "agent_b", {"step": 2, "prev": "A"}
    )
    
    # Verify order
    history = await get_spawn_history(parent_id)
    assert history[0].agent_type == "agent_a"
    assert history[1].agent_type == "agent_b"

async def test_parallel_join():
    """Test parallel-join pattern with supervisor."""
    parent_id = "parent-parallel"
    
    # Spawn with supervisor
    result = await spawn_service.spawn_with_supervisor(
        parent_session_id=parent_id,
        children_configs=[
            ChildConfig(agent_type="agent_a"),
            ChildConfig(agent_type="agent_b"),
            ChildConfig(agent_type="agent_c"),
        ],
        coordination_pattern="parallel_join",
    )
    
    # Simulate all children completing
    for child in result.children:
        await simulate_child_completion(child.session_id)
    
    # Verify supervisor detected join
    status = await get_coordination_status(result.supervisor_session_id)
    assert status.state == "COMPLETED"
```

### 12.3 E2E Tests

```python
# backend/tests/multi_agent/test_e2e_skill_creation.py

async def test_e2e_skill_creation_with_dependencies():
    """
    End-to-end test: Create skill that requires MCP + tool.
    
    This tests the full flow:
    1. Parent skill agent analyzes requirements
    2. Spawns MCP builder child
    3. Spawns tool builder child
    4. Both complete
    5. Parent resumes with both dependencies ready
    """
    # Start skill creation
    skill_session = await start_skill_creation(
        "Create email marketing skill"
    )
    
    # Analyze should detect dependencies
    analysis = await analyze_requirements(skill_session)
    assert analysis.needs_mcp
    assert analysis.needs_tools
    
    # Spawn children
    children = await spawn_dependencies(skill_session, analysis)
    assert len(children) == 2
    
    # Simulate children completing
    for child in children:
        await complete_child_work(child.session_id)
    
    # Verify parent receives completion
    events = await poll_events(skill_session)
    completion_events = [e for e in events if e.type == "child_completed"]
    assert len(completion_events) == 2
    
    # Verify parent can continue
    parent_state = await get_session_state(skill_session)
    assert parent_state.can_continue
```

---

## 13. Open Questions & Future Work

### 13.1 Open Questions for v1.5

| Question | Current Thinking | Decision Needed By |
|----------|------------------|-------------------|
| WebSocket vs polling for events? | Start with polling, add WebSocket later | Phase 2 |
| Should children see sibling state? | No (isolation), but via workspace service if needed | Phase 1 |
| How to handle parent crash? | Sessions remain, supervisor takes over if exists | Phase 3 |
| Session timeout behavior? | Configurable, default 5 min inactivity | Phase 1 |
| Workspace size limits? | 1MB JSONB limit (PostgreSQL), enforce in code | Phase 1 |

### 13.2 Future Work (v1.6+)

| Feature | Description | Priority |
|---------|-------------|----------|
| **Cyclic Graphs** | Allow cycles (A → B → A) for iterative refinement | Medium |
| **WebSocket Events** | Real-time push instead of polling | Medium |
| **Distributed Sessions** | Run children on different backend instances | Low |
| **Agent Marketplace** | Spawn agents from marketplace templates | Medium |
| **Advanced Circuit Breaker** | Per-dependency CB with automatic recovery | Low |
| **Performance Metrics** | Detailed latency, throughput analytics | Medium |
| **Visual Orchestration** | Canvas-based workflow designer for agents | High |

### 13.3 Known Limitations

| Limitation | Rationale | Mitigation |
|------------|-----------|------------|
| DAG-only (no cycles) | Simpler implementation, easier reasoning | Explicit error if cycle detected |
| Max depth 3 (configurable) | Prevent runaway spawning | Configurable limit, error on exceed |
| PostgreSQL event persistence | Durability over performance | Redis for real-time optimization |
| No cross-user sessions | Security isolation | Each user's sessions isolated |

---

## 14. Appendix

### 14.1 Glossary

| Term | Definition |
|------|------------|
| **Session** | A running agent instance with its own state, checkpointer, and UI tab |
| **Parent** | The agent that spawned a child session |
| **Child** | A session spawned by a parent agent |
| **Supervisor** | An optional agent that manages complex coordination patterns |
| **Workspace** | Shared state accessible to parent and children |
| **Coordination Pattern** | Predefined strategy for managing multiple children (sequential, parallel, etc.) |
| **Event** | Notification of state change (child completed, workspace updated, etc.) |
| **DAG** | Directed Acyclic Graph — graph with no cycles |

### 14.2 Related Topics

| Topic | Relationship |
|-------|--------------|
| Topic #16 | Foundation: Multi-Agent Tab Architecture |
| Topic #21 | Universal Integration (tools used by agents) |
| Topic #23 | Plugin Templates (spawn template instances) |
| Topic #24 | Third-Party Apps UI (child agent use case) |

### 14.3 References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- LangGraph Subgraphs: https://langchain-ai.github.io/langgraph/concepts/subgraphs/
- Redis Pub/Sub: https://redis.io/docs/manual/pubsub/
- PostgreSQL JSONB: https://www.postgresql.org/docs/current/datatype-json.html

---

*Document Version: 1.0*
*Last Updated: 2026-03-15*
*Target Release: AgentOS v1.5*
