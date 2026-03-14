# Enhancement Documentation

This directory contains enhancement proposals and detailed implementation plans for major Blitz AgentOS features.

## Active Brainstorming

📋 **[BRAINSTORMING-TRACKING.md](BRAINSTORMING-TRACKING.md)** — Live tracking of all v1.4+ topics

See the tracking document for:
- All pending topics with priorities
- Completed brainstorming with design docs
- Topic selection guide for next sessions

---

## Current Proposals

### 1. Runtime Permission Approval (HITL) ⭐ NEW

**Status:** ✅ Design Complete  
**Priority:** High  
**Target:** v1.4

Transform Gate 3 (Tool ACL) from binary deny into escalatable Human-in-the-Loop permission approval. When a skill attempts to use a tool the user lacks permission for, execution pauses, notifies an admin, and resumes automatically upon approval.

**Key Capabilities:**
- Runtime permission requests with rich context
- One-click approval with duration options (session/72h/permanent)
- Auto-approve rule engine with conditions
- Configurable timeout with escalation
- Works in both Keycloak and local auth modes

**Documentation:**
- [00-specification.md](runtime-permission-approval/00-specification.md) - Complete design specification

---

### 2. Admin Registry Edit UI ⭐ NEW

**Status:** ✅ Design Complete  
**Priority:** High  
**Target:** v1.4

Create comprehensive detail and edit pages for all registry types (agents, tools, MCP servers, skills) with form-based editing instead of raw JSON. Include test/preview functionality for MCP server connections and dual pagination for better navigation.

**Key Capabilities:**
- Form-based editing for all registry configuration (no more JSON-only)
- Detail pages for agents, tools, MCP servers (skills enhanced)
- Name/slug immutable (display name editable)
- MCP server connection test before saving
- Dual pagination (top + bottom) on all list pages
- Consistent navigation patterns across all registry types

**Documentation:**
- [00-specification.md](admin-registry-edit-ui/00-specification.md) - Complete design specification

---

### 3. Advanced User & Group Management ⭐ NEW

**Status:** ✅ Design Complete  
**Priority:** High  
**Target:** v1.4

Transform AgentOS user management into an enterprise-grade identity system with direct group-based permissions and seamless external identity provider integration (Keycloak/AD/LDAP). Features clear separation between Identity (external) and Permissions (AgentOS-local).

**Key Capabilities:**
- Direct group permissions (no role indirection)
- Global Groups (read-only mirror of Keycloak/AD)
- Local Groups (permission-bearing with external mappings)
- Group detail pages with Members/Permissions/Settings tabs
- "Manage Groups" modal for user group assignment
- Auto-provisioning based on external group membership
- Permission visibility by category
- Manual and synced group membership tracking

**Documentation:**
- [00-specification.md](advanced-user-group-management/00-specification.md) - Complete design specification

---

### 4. Admin Console LLM Configuration ⭐ NEW

**Status:** ✅ Design Complete  
**Priority:** High  
**Target:** v1.4

Transform LiteLLM configuration from file-based, restart-required workflow into a dynamic, UI-driven operational experience. Features a pluggable module architecture that enables runtime model management, fallback chains, health monitoring, and cost tracking—all from the Admin Console.

**Key Capabilities:**
- Runtime model management (add/edit/remove without restart)
- One-click model connectivity testing
- Visual fallback chain builder with condition-based routing
- Real-time health monitoring with latency/error metrics
- Cost tracking with budget alerts and quotas
- Pluggable BaseModule architecture for future extensions
- Scales from 100 users (Docker Compose) to 5,000+ (Kubernetes)

**Documentation:**
- [00-specification.md](admin-console-llm-config/00-specification.md) - Complete design specification

---

### 5. AgentOS Dashboard & Mission Control ⭐ NEW

**Status:** ✅ Design Complete  
**Priority:** High  
**Target:** v1.4

A comprehensive operational dashboard providing real-time visibility into agent activities, workflow executions, system health, and memory management. Drawing inspiration from OpenClaw Dashboard implementations, this creates a unified Mission Control interface integrated into the AgentOS frontend.

**Key Capabilities:**
- Real-time activity feed of agent actions and workflow executions
- Flow execution monitor with step-by-step drill-down and error analysis
- Agent management with optional 3D office visualization
- Memory browser with full-text and semantic search
- Deep integration with existing Phase 8 observability (Prometheus, Grafana, Loki)
- WebSocket-based real-time updates
- Unified interface for both admins and end users

**Documentation:**
- [00-specification.md](agentos-dashboard-mission-control/00-specification.md) - Complete design specification

---

### 6. Scheduler Engine & UI ⭐ NEW

**Status:** ✅ Design Complete  
**Priority:** High  
**Target:** v1.4

A comprehensive scheduler management interface that transforms AgentOS's existing Celery-based background task system into a fully visible, manageable, and interactive scheduling platform. Features global scheduler view, per-workflow schedule management, visual cron builder, and multi-channel alerting.

**Key Capabilities:**
- Global scheduler view for operations (/scheduler)
- Per-workflow schedule tab for user management
- Interactive visual cron builder with timezone support
- Job execution history with drill-down details
- Real-time queue monitoring (Celery queue depth, worker status)
- Multi-channel alerting (in-app, Telegram, email) for job failures
- Manual "Run Now" for ad-hoc execution
- Enable/disable jobs with one click
- Step-by-step execution visibility

**Documentation:**
- [00-specification.md](scheduler-engine-ui/00-specification.md) - Complete design specification

---

### 7. Security Scan Module

**Status:** Planning Complete  
**Priority:** High  
**Target:** v1.4

A standalone, independently maintainable security scanning service that integrates with AgentOS via MCP protocol.

**Key Capabilities:**
- Dependency vulnerability scanning (pip-audit)
- Secret detection (detect-secrets)
- Static code analysis (bandit)
- Policy-based validation
- Workflow security gates
- Skill import scanning

**Documentation:**
- [00-specification.md](security-scan-module/00-specification.md) - Technical specification
- [01-implementation-phases.md](security-scan-module/01-implementation-phases.md) - 4-phase roadmap
- [02-component-specs.md](security-scan-module/02-component-specs.md) - Component details
- [03-integration-guide.md](security-scan-module/03-integration-guide.md) - Integration steps
- [04-deployment-guide.md](security-scan-module/04-deployment-guide.md) - Deployment procedures
- [05-testing-strategy.md](security-scan-module/05-testing-strategy.md) - Testing approach
- [README.md](security-scan-module/README.md) - Quick start guide

---

## Document Template

When adding new enhancement documentation, please follow this structure:

```
docs/enhancement/
└── feature-name/
    ├── README.md                 # Quick start and overview
    ├── 00-specification.md       # Technical specification
    ├── 01-implementation-phases.md # Roadmap and phases
    ├── 02-component-specs.md     # Component details
    ├── 03-integration-guide.md   # Integration steps
    ├── 04-deployment-guide.md    # Deployment guide
    └── 05-testing-strategy.md    # Testing approach
```

---

## Contributing

When proposing new enhancements:

1. Create a new directory under `docs/enhancement/`
2. Follow the document template above
3. Include architecture diagrams
4. Define clear success criteria
5. Identify risks and mitigations
6. Get stakeholder sign-off before implementation

---

**Maintained by:** Blitz AgentOS Architecture Team  
**Last Updated:** 2026-03-16
