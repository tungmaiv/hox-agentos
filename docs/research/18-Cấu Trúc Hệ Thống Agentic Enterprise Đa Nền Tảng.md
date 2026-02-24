Based on the sources and our technical discussion, here is a comprehensive folder structure designed for your enterprise agentic application. This structure separates the **Next.js Frontend** (Client Skills & UI) from the **Python/FastAPI Backend** (Orchestration, Gateway, and Backend Tools) to support on-premise deployment, multi-user isolation, and clear categorization of agentic components 1-3.

### Project Root Structure

root/  
├── docker-compose.yml          \# Infrastructure: Postgres, Keycloak, Redis \[Proposed Solution\]  
├── .env                        \# Root environment variables (API keys, DB secrets) \[4\]  
├── backend/                    \# Python FastAPI Backend (Orchestrator & Runtime)  
└── frontend/                   \# Next.js Frontend (CopilotKit & Agentic UI)

### I. Backend Structure (Python/FastAPI)

The backend serves as the **Central Nervous System**, hosting the LangGraph logic and the Copilot Runtime 3, 5\.  
backend/  
├── main.py                     \# Entry point for FastAPI server \[6\]  
├── core/                       \# THE CORE: Shared logic and Pydantic models  
│   ├── schemas/                \# Pydantic models for data validation \[7, 8\]  
│   ├── memory/                 \# Hierarchical memory management (User-specific) \[9\]  
│   └── security/               \# Keycloak JWT verification and RBAC logic \[Proposed Solution\]  
├── gateway/                    \# THE GATEWAY: Copilot Runtime & Security Proxy  
│   ├── runtime.py              \# Copilot Runtime SDK initialization \[5, 10\]  
│   └── middleware/             \# AG-UI Middleware for ACL/RBAC checking \[234, Proposed Solution\]  
├── channels/                   \# THE CHANNELS: Adapters for Slack, Teams, or WebChat \[11, 12\]  
│   └── whatsapp/               \# (Optional) OpenClaw-style channel connectors \[13\]  
├── agents/                     \# THE AGENTS: LangGraph StateGraphs and Deep Agents  
│   ├── master\_agent.py         \# Main orchestrator using create\_deep\_agent \[14, 15\]  
│   ├── sub\_agents/             \# Specialized sub-agent definitions \[16, 17\]  
│   └── graphs.py               \# StateGraph node and edge definitions \[14, 18\]  
├── tools/                      \# THE TOOLS: Backend-side Python tools (@tool)  
│   ├── data\_ops.py             \# Database query and file processing tools \[19, 20\]  
│   └── sandbox/                \# Docker Sandboxing logic for tool execution \[21\]  
└── mcp/                        \# THE MCP: Integration for Model Context Protocol  
    ├── client.py               \# MCP Client to connect to external servers \[22\]  
    └── servers/                \# Local MCP server logic (e.g., enterprise DB access) \[22, 23\]

### II. Frontend Structure (Next.js/TypeScript)

The frontend handles the **Agent-User Interaction (AG-UI)**, UI rendering, and client-side "Skills" 1, 24, 25\.  
frontend/  
├── src/  
│   ├── app/  
│   │   ├── api/copilotkit/     \# Proxy route connecting to backend runtime \[26, 27\]  
│   │   ├── layout.tsx          \# CopilotKit Provider setup with Keycloak context \[28, 29\]  
│   │   └── page.tsx            \# Main canvas/chat interface \[30\]  
│   ├── components/  
│   │   ├── canvas/             \# Low-code drag-and-drop canvas components \[31, 32\]  
│   │   ├── chat/               \# Custom CopilotChat or Popup components \[33\]  
│   │   └── a2ui/               \# A2UIMessageRenderer and dynamic widgets \[34, 35\]  
│   ├── hooks/                  \# THE SKILLS: Client-side tools/actions  
│   │   ├── use-frontend-tools.ts \# Registration of UI-modifying skills \[36-38\]  
│   │   ├── use-acl.ts          \# Custom hook to toggle 'available' property \[39\]  
│   │   └── use-co-agent.ts     \# Shared State synchronization hooks \[40, 41\]  
│   └── lib/  
│       ├── types/              \# TypeScript interfaces and A2UI specs \[42\]  
│       └── utils/              \# Client-side helper functions  
└── tailwind.config.ts          \# Styling for Generative UI components \[43\]

### III. Component Mapping and Functional Logic

* **Core**: This directory houses your **Pydantic Models**. For an enterprise app, it is vital to have a strict schema for every tool input, output, and memory entry to ensure "Type Safety" across the agentic loop 7, 8, 44\.  
* **Gateway**: This is where you implement the **@copilotkit/runtime**. It acts as a security proxy, ensuring that Keycloak roles are checked via **AG-UI Middleware** before a TOOL\_CALL\_START event is processed 232, 234, Proposed Solution.  
* **Channel**: Following the **OpenClaw** paradigm, this folder is used if your agent needs to interact with users outside of your Next.js app (e.g., relaying messages to Slack or WhatsApp) 11, 12\.  
* **Agent**: This stores your **LangGraph** definitions. You should separate "Deep Agents" (which handle planning and file management) into their own sub-folder to manage multi-step reasoning complexity 6, 14, 15\.  
* **Skill**: In the CopilotKit stack, "Skills" are typically **Frontend Tools** defined using useFrontendTool (v2). They allow the agent to interact with browser-side primitives like localStorage, React state, or UI animations 36-38.  
* **Tool**: These are **Backend Tools** written in Python and decorated with @tool. They perform sensitive operations like database queries or calling internal APIs that must remain on the secure on-premise server 19, 45, 46\.  
* **MCP**: This directory contains the logic for the **Model Context Protocol**. It allows your agents to dynamically discover and use external toolsets (like Google Drive or GitHub) through standardized MCP servers 22, 23\.

**Recommendation for Implementation:**Start by setting up the gateway/ and app/api/copilotkit/ route to establish the bi-directional connection. Then, use the **LangGraph AG-UI Canvas Starter** pattern to populate the frontend/src/components/canvas/ and backend/agents/ folders, ensuring that your state is shared bidirectionally via useCoAgent 31, 41, 47\.  
