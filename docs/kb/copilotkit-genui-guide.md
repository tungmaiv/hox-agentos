# CopilotKit Generative UI Implementation Guide

A comprehensive technical guide for building applications with all three types of Generative UI (GenUI) using CopilotKit.

## Overview

This guide is based on analysis of the [CopilotKit generative-ui-playground](https://github.com/CopilotKit/generative-ui-playground/) repository, which demonstrates three approaches to building AI-powered user interfaces:

| UI Type | Description | Use Case | Technology |
|---------|-------------|----------|------------|
| **Static GenUI** | Pre-built React components rendered by frontend hooks | Weather cards, stock displays, task approvals | `useFrontendTool`, `useHumanInTheLoop` |
| **MCP Apps** | HTML/JS apps served by MCP servers in sandboxed iframes | Flight booking, hotel search, trading simulator | MCP Server + `MCPAppsMiddleware` |
| **A2UI** | Agent-composed declarative JSON UI rendered dynamically | Restaurant finder, booking forms | A2A Agent + `A2UIRenderer` |

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Static GenUI Implementation](#2-static-genui-implementation)
3. [MCP Apps Implementation](#3-mcp-apps-implementation)
4. [A2UI Implementation](#4-a2ui-implementation)
5. [Complete Project Setup](#5-complete-project-setup)
6. [Best Practices & Tips](#6-best-practices--tips)

---

## 1. Architecture Overview

### 1.1 System Architecture

```
Frontend (Next.js) ─────────────────────────────────────────────────────
├── Protocol tabs switch between agents
├── Static GenUI: useFrontendTool, useHumanInTheLoop
├── MCP Apps: Automatic iframe rendering via middleware events
└── A2UI: A2UIRenderer for declarative JSON
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   "default" Agent      "a2ui" Agent
   BasicAgent + MCP     HttpAgent → Python
   Port 3001            Port 10002
```

### 1.2 Key Dependencies

```json
{
  "dependencies": {
    "@copilotkitnext/react": "1.51.0-next.4",
    "@copilotkitnext/runtime": "1.51.0-next.4",
    "@copilotkit/a2ui-renderer": "0.0.2",
    "@ag-ui/a2a": "0.0.6",
    "@ag-ui/mcp-apps-middleware": "0.0.1",
    "@a2ui/lit": "0.8.1",
    "@modelcontextprotocol/sdk": "latest",
    "zod": "^3.25.76"
  }
}
```

### 1.3 Environment Variables

```env
OPENAI_API_KEY=sk-your-key-here
MCP_SERVER_URL=http://localhost:3001/mcp
A2A_AGENT_URL=http://localhost:10002
```

---

## 2. Static GenUI Implementation

Static GenUI uses pre-built React components that are defined in the frontend and rendered when specific tools are called by the agent.

### 2.1 Core Concepts

- **`useFrontendTool`**: Defines callable tools with handlers and custom rendering
- **`useHumanInTheLoop`**: Interactive prompts requiring user input (approvals, confirmations)
- **Tool Registration**: Frontend defines tools with Zod schemas for parameters

### 2.2 Implementation Steps

#### Step 1: Create the Context Provider

Create a provider component that registers all Static GenUI tools:

```tsx
// src/app/components/CopilotContextProvider.tsx
"use client";

import { useFrontendTool, useHumanInTheLoop } from "@copilotkitnext/react";
import { z } from "zod";
import { WeatherCard, WeatherLoadingState } from "./static-tools/WeatherCard";

// Type definitions for tool results
type WeatherData = {
  location: string;
  temperature: number;
  conditions: string;
  humidity: number;
  windSpeed: number;
};

export function CopilotContextProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  // Weather tool - callable tool that displays weather data
  useFrontendTool({
    name: "get_weather",
    description: "Get current weather information for a location",
    parameters: z.object({
      location: z.string().describe("The city or location to get weather for"),
    }),
    handler: async ({ location }) => {
      // Simulate API delay
      await new Promise((resolve) => setTimeout(resolve, 500));
      return getMockWeather(location); // Your data fetching logic
    },
    render: ({ status, args, result }) => {
      // Loading state
      if (status === "inProgress" || status === "executing") {
        return <WeatherLoadingState location={args?.location} />;
      }

      // Complete state with results
      if (status === "complete" && result) {
        const data = JSON.parse(result) as WeatherData;
        return (
          <WeatherCard
            location={data.location}
            temperature={data.temperature}
            conditions={data.conditions}
            humidity={data.humidity}
            windSpeed={data.windSpeed}
          />
        );
      }

      return <></>;
    },
  });

  // Task approval - human-in-the-loop pattern
  useHumanInTheLoop({
    name: "approve_task",
    description: "Request user approval for a task before executing it",
    parameters: z.object({
      taskTitle: z.string().describe("The title of the task requiring approval"),
      taskDescription: z.string().describe("Detailed description of what the task will do"),
      impact: z.string().describe("The impact or scope of the task").optional(),
    }),
    render: ({ args, status, respond, result }) => {
      // Show approval UI when waiting for user input
      if (status === "executing" && respond) {
        return (
          <TaskApprovalCard
            taskTitle={args.taskTitle}
            taskDescription={args.taskDescription}
            impact={args.impact}
            onApprove={() => respond({ approved: true })}
            onReject={() => respond({ approved: false })}
          />
        );
      }

      // Show result after user has responded
      if (status === "complete" && result) {
        const data = JSON.parse(result) as { approved: boolean };
        return (
          <div className="glass-card p-4">
            {data.approved ? (
              <span className="text-green-600">Task Approved</span>
            ) : (
              <span className="text-red-600">Task Rejected</span>
            )}
          </div>
        );
      }

      return <></>;
    },
  });

  return <>{children}</>;
}
```

#### Step 2: Create UI Components

```tsx
// src/app/components/static-tools/WeatherCard.tsx
"use client";

interface WeatherCardProps {
  location: string;
  temperature: number;
  conditions: string;
  humidity?: number;
  windSpeed?: number;
  icon?: string;
}

function getWeatherIcon(conditions: string): string {
  const lower = conditions.toLowerCase();
  if (lower.includes("sun") || lower.includes("clear")) return "☀️";
  if (lower.includes("cloud")) return "☁️";
  if (lower.includes("rain")) return "🌧️";
  if (lower.includes("snow")) return "❄️";
  return "🌤️";
}

export function WeatherCard({
  location,
  temperature,
  conditions,
  humidity,
  windSpeed,
}: WeatherCardProps) {
  const weatherIcon = getWeatherIcon(conditions);

  return (
    <div className="glass-card p-5 max-w-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold">{location}</h3>
          <p className="text-sm text-gray-500">Current Weather</p>
        </div>
        <div className="text-4xl">{weatherIcon}</div>
      </div>

      <div className="mb-4">
        <span className="text-5xl font-bold">{Math.round(temperature)}°</span>
        <span className="text-xl text-gray-500 ml-1">F</span>
      </div>

      <p className="font-medium mb-4">{conditions}</p>

      <div className="flex gap-6 pt-4 border-t border-gray-200">
        {humidity !== undefined && (
          <div>
            <p className="text-xs text-gray-400">Humidity</p>
            <p className="text-sm font-medium">{humidity}%</p>
          </div>
        )}
        {windSpeed !== undefined && (
          <div>
            <p className="text-xs text-gray-400">Wind</p>
            <p className="text-sm font-medium">{windSpeed} mph</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function WeatherLoadingState({ location }: { location?: string }) {
  return (
    <div className="glass-card p-5 max-w-sm animate-pulse">
      <div className="h-5 w-32 bg-gray-200 rounded mb-2" />
      <div className="h-12 w-24 bg-gray-200 rounded" />
      {location && (
        <p className="text-xs text-gray-400 mt-3">
          Loading weather for {location}...
        </p>
      )}
    </div>
  );
}
```

#### Step 3: Wrap Your App with Provider

```tsx
// src/app/page.tsx
"use client";

import { CopilotKitProvider, CopilotSidebar } from "@copilotkitnext/react";
import { CopilotContextProvider } from "./components/CopilotContextProvider";
import "@copilotkitnext/react/styles.css";

export default function Home() {
  return (
    <CopilotKitProvider runtimeUrl="/api/copilotkit" showDevConsole={false}>
      <CopilotContextProvider>
        <main>
          {/* Your app content */}
        </main>
        <CopilotSidebar
          defaultOpen={true}
          labels={{
            modalHeaderTitle: "Static GenUI Demo",
            chatInputPlaceholder: "Ask about weather or request task approvals!",
          }}
        />
      </CopilotContextProvider>
    </CopilotKitProvider>
  );
}
```

### 2.3 API Route Setup

Create the CopilotKit API route for handling agent communication:

```tsx
// src/app/api/copilotkit/route.ts
import { NextRequest } from "next/server";
import { CopilotRuntime, OpenAIAdapter } from "@copilotkitnext/runtime";

const copilotKit = new CopilotRuntime({
  // Configure your LLM adapter
});

export async function POST(req: NextRequest) {
  return copilotKit.handleRequest(req);
}
```


---

## 3. MCP Apps Implementation

MCP Apps are interactive HTML/JS applications served by MCP (Model Context Protocol) servers and rendered in sandboxed iframes.

### 3.1 Core Concepts

- **MCP Server**: Express server exposing tools and UI resources
- **UI Resources**: HTML files with `text/html+mcp` MIME type
- **StreamableHTTP Transport**: HTTP-based MCP transport with session management
- **Resource URI Metadata**: Links tools to their UI resources

### 3.2 Implementation Steps

#### Step 1: Create MCP Server

```typescript
// mcp-server/server.ts
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import express, { Request, Response } from "express";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { isInitializeRequest, Resource } from "@modelcontextprotocol/sdk/types.js";
import { InMemoryEventStore } from "@modelcontextprotocol/sdk/examples/shared/inMemoryEventStore.js";
import cors from "cors";
import fs from "node:fs/promises";
import path from "node:path";

const RESOURCE_URI_META_KEY = "ui/resourceUri";

// Store active sessions
const activeSessions: Map<string, any> = new Map();

// Load UI HTML files
const loadHtml = async (name: string): Promise<string> => {
  const htmlPath = path.join(__dirname, "apps", `${name}.html`);
  try {
    return await fs.readFile(htmlPath, "utf-8");
  } catch {
    return `<!DOCTYPE html>
<html>
<head><title>${name}</title></head>
<body>
  <div style="padding: 20px;">
    <h2>${name} Loading...</h2>
  </div>
</body>
</html>`;
  }
};

// Create MCP server
const getServer = async () => {
  const server = new McpServer(
    {
      name: "ui-apps-mcp-server",
      version: "1.0.0",
    },
    { capabilities: { logging: {} } }
  );

  // Load app HTML
  const calculatorHtml = await loadHtml("calculator");

  // Register UI resource
  const calculatorResource: Resource = {
    name: "calculator-app-template",
    uri: "ui://calculator/calculator.html",
    title: "Calculator",
    description: "Interactive calculator with memory and history",
    mimeType: "text/html+mcp",
  };

  server.registerResource(
    calculatorResource.name,
    calculatorResource.uri,
    calculatorResource,
    async () => ({
      contents: [{
        uri: calculatorResource.uri,
        mimeType: calculatorResource.mimeType,
        text: calculatorHtml,
      }],
    })
  );

  // Register main tool with UI resource link
  server.registerTool(
    "open_calculator",
    {
      title: "Open Calculator",
      description: "Opens an interactive calculator",
      inputSchema: {},
      _meta: {
        [RESOURCE_URI_META_KEY]: calculatorResource.uri,
      },
    },
    async (): Promise<CallToolResult> => {
      const sessionId = randomUUID();
      const state = { display: "0", history: [] };
      activeSessions.set(sessionId, state);

      return {
        content: [{ type: "text", text: "Calculator opened" }],
        structuredContent: {
          sessionId,
          state,
        },
      };
    }
  );

  // Register helper tool for button presses
  server.registerTool(
    "calculator_input",
    {
      title: "Calculator Input",
      description: "Send input to calculator",
      inputSchema: {
        sessionId: z.string(),
        input: z.string(), // digit, operator, or command
      },
    },
    async ({ sessionId, input }): Promise<CallToolResult> => {
      const state = activeSessions.get(sessionId);
      if (!state) {
        return {
          content: [{ type: "text", text: "Session not found" }],
          structuredContent: { success: false },
        };
      }

      // Process input and update state
      // ... calculator logic ...

      return {
        content: [{ type: "text", text: `Input: ${input}` }],
        structuredContent: {
          success: true,
          state,
        },
      };
    }
  );

  return server;
};

// Setup Express server
const app = express();
app.use(express.json());
app.use(cors({ origin: "*", exposedHeaders: ["Mcp-Session-Id"] }));

const transports: { [sessionId: string]: StreamableHTTPServerTransport } = {};

// MCP POST handler
const mcpPostHandler = async (req: Request, res: Response) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;

  try {
    let transport: StreamableHTTPServerTransport;

    if (sessionId && transports[sessionId]) {
      transport = transports[sessionId];
    } else if (!sessionId && isInitializeRequest(req.body)) {
      const eventStore = new InMemoryEventStore();
      transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        eventStore,
        onsessioninitialized: (sid) => {
          console.log(`[MCP] Session initialized: ${sid}`);
          transports[sid] = transport;
        },
      });

      transport.onclose = () => {
        const sid = transport.sessionId;
        if (sid && transports[sid]) {
          delete transports[sid];
        }
      };

      const server = await getServer();
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
      return;
    } else {
      res.status(400).json({
        jsonrpc: "2.0",
        error: { code: -32000, message: "Bad Request: No valid session ID" },
        id: null,
      });
      return;
    }

    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    console.error("[MCP] Error:", error);
    res.status(500).json({
      jsonrpc: "2.0",
      error: { code: -32603, message: "Internal server error" },
      id: null,
    });
  }
};

// Routes
app.post("/mcp", mcpPostHandler);

app.get("/mcp", async (req: Request, res: Response) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  if (!sessionId || !transports[sessionId]) {
    res.status(400).send("Invalid session ID");
    return;
  }
  await transports[sessionId].handleRequest(req, res);
});

app.listen(3001, () => {
  console.log(`[MCP Server] Running at http://localhost:3001/mcp`);
});
```

#### Step 2: Create HTML App

```html
<!-- mcp-server/apps/calculator.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Calculator</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 20px;
      background: #f5f5f5;
    }
    .calculator {
      max-width: 300px;
      margin: 0 auto;
      background: white;
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .display {
      background: #1a1a1a;
      color: white;
      padding: 20px;
      border-radius: 8px;
      text-align: right;
      font-size: 2rem;
      margin-bottom: 15px;
      min-height: 60px;
    }
    .buttons {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }
    button {
      padding: 20px;
      font-size: 1.2rem;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      background: #e0e0e0;
    }
    button.operator { background: #ff9500; color: white; }
    button.equals { background: #34c759; color: white; }
    button.clear { background: #ff3b30; color: white; }
  </style>
</head>
<body>
  <div class="calculator">
    <div class="display" id="display">0</div>
    <div class="buttons">
      <button class="clear" onclick="sendInput('C')">C</button>
      <button onclick="sendInput('(')">(</button>
      <button onclick="sendInput(')')">)</button>
      <button class="operator" onclick="sendInput('/')">÷</button>
      
      <button onclick="sendInput('7')">7</button>
      <button onclick="sendInput('8')">8</button>
      <button onclick="sendInput('9')">9</button>
      <button class="operator" onclick="sendInput('*')">×</button>
      
      <button onclick="sendInput('4')">4</button>
      <button onclick="sendInput('5')">5</button>
      <button onclick="sendInput('6')">6</button>
      <button class="operator" onclick="sendInput('-')">−</button>
      
      <button onclick="sendInput('1')">1</button>
      <button onclick="sendInput('2')">2</button>
      <button onclick="sendInput('3')">3</button>
      <button class="operator" onclick="sendInput('+')">+</button>
      
      <button onclick="sendInput('0')" style="grid-column: span 2;">0</button>
      <button onclick="sendInput('.')">.</button>
      <button class="equals" onclick="sendInput('=')">=</button>
    </div>
  </div>

  <script>
    // Get session ID from URL params
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get('session');

    async function sendInput(input) {
      try {
        const response = await fetch('/mcp', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Mcp-Session-Id': sessionId,
          },
          body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'tools/call',
            params: {
              name: 'calculator_input',
              arguments: { sessionId, input },
            },
            id: Date.now(),
          }),
        });

        const data = await response.json();
        if (data.result?.content) {
          updateDisplay(data.result.content.structuredContent?.state?.display || input);
        }
      } catch (error) {
        console.error('Error:', error);
      }
    }

    function updateDisplay(value) {
      document.getElementById('display').textContent = value;
    }
  </script>
</body>
</html>
```


#### Step 3: Configure Frontend for MCP

```tsx
// src/app/page.tsx (with MCP support)
"use client";

import { CopilotKitProvider, CopilotSidebar } from "@copilotkitnext/react";
import { useMCPAppsMiddleware } from "@ag-ui/mcp-apps-middleware";
import "@copilotkitnext/react/styles.css";

export default function Home() {
  // Enable MCP Apps middleware
  useMCPAppsMiddleware({
    mcpServerUrl: process.env.NEXT_PUBLIC_MCP_SERVER_URL || "http://localhost:3001/mcp",
  });

  return (
    <CopilotKitProvider runtimeUrl="/api/copilotkit" showDevConsole={false}>
      <main>
        {/* Your app content */}
        <p>Try: "Open the calculator" or "Search for flights to Paris"</p>
      </main>
      <CopilotSidebar
        defaultOpen={true}
        labels={{
          modalHeaderTitle: "MCP Apps Demo",
          chatInputPlaceholder: "Ask to open interactive apps!",
        }}
      />
    </CopilotKitProvider>
  );
}
```

---

## 4. A2UI Implementation

A2UI (Agent-to-User Interface) uses declarative JSON that agents generate to render dynamic UIs. The backend agent produces A2UI-compliant JSON, which the frontend renders using specialized components.

### 4.1 Core Concepts

- **A2A Protocol**: Agent-to-Agent communication protocol
- **A2UI Schema**: JSON schema for declarative UI components
- **A2UIRenderer**: Frontend component that renders A2UI JSON
- **A2UI Theme**: Styling configuration for rendered components

### 4.2 Implementation Steps

#### Step 1: Create Python A2A Agent

```python
# a2a-agent/agent/agent.py
import json
import os
from typing import AsyncIterable, Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.genai import types
import jsonschema

AGENT_INSTRUCTION = """
You are a UI generation assistant. You create user interfaces using A2UI declarative JSON.

**Your capabilities:**
- Forms: Contact forms, signup forms, surveys, settings panels
- Lists: Todo lists, shopping lists, search results
- Cards: Profile cards, product cards, info cards
- Confirmations: Success messages, error alerts

**How to generate UI:**
1. Listen to what UI the user wants
2. Generate valid A2UI JSON following the schema
3. Wrap JSON with delimiter: ---a2ui_JSON---

**Response format:**
<text response for the user>
---a2ui_JSON---
<A2UI JSON array>
"""

# A2UI Schema (simplified - use full schema in production)
A2UI_SCHEMA = '''
{
  "type": "object",
  "properties": {
    "type": { "enum": ["card", "form", "list", "text"] },
    "components": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": { "type": "string" },
          "properties": { "type": "object" }
        }
      }
    }
  }
}
'''


class UIGeneratorAgent:
    """Agent that generates UIs using A2UI declarative JSON."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self._agent = self._build_agent()
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
        self._user_id = "remote_agent"

    def _build_agent(self) -> LlmAgent:
        LITELLM_MODEL = os.getenv("LITELLM_MODEL", "openai/gpt-4")

        return LlmAgent(
            model=LiteLlm(model=LITELLM_MODEL),
            name="ui_generator_agent",
            description="An agent that generates UIs using A2UI declarative JSON.",
            instruction=AGENT_INSTRUCTION,
            tools=[],
        )

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict[str, Any]]:
        """Stream agent responses."""
        session = await self._runner.session_service.get_session(
            app_name=self._agent.name,
            user_id=self._user_id,
            session_id=session_id,
        )

        if session is None:
            session = await self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                session_id=session_id,
            )

        current_message = types.Content(
            role="user", parts=[types.Part.from_text(text=query)]
        )

        async for event in self._runner.run_async(
            user_id=self._user_id,
            session_id=session.id,
            new_message=current_message,
        ):
            if event.is_final_response():
                content = ""
                if event.content and event.content.parts:
                    content = "\n".join([p.text for p in event.content.parts if p.text])

                yield {
                    "is_task_complete": True,
                    "content": content,
                }
            else:
                yield {
                    "is_task_complete": False,
                    "updates": "Generating UI...",
                }
```

#### Step 2: Create A2A Server Entry Point

```python
# a2a-agent/agent/__main__.py
import logging
import os
import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

from .agent import UIGeneratorAgent
from .a2ui_extension import get_a2ui_agent_extension

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_agent_card(base_url: str) -> AgentCard:
    return AgentCard(
        name="UI Generator",
        description="A general-purpose AI assistant that creates dynamic user interfaces.",
        url=base_url,
        version="1.0.0",
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=False,
            state_transition_history=False,
            extensions=[get_a2ui_agent_extension()],
        ),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="create_form",
                name="Create Forms",
                description="Generate contact forms, signup forms, surveys",
                tags=["forms", "input"],
                examples=["Create a contact form"],
            ),
        ],
    )


@click.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=10002, envvar="PORT")
def main(host: str, port: int):
    base_url = os.getenv("A2A_BASE_URL", f"http://localhost:{port}")
    logger.info(f"Starting UI Generator agent at {base_url}")

    agent_card = create_agent_card(base_url)
    executor = UIGeneratorAgent(base_url=base_url)

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    app = server.build()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
```

#### Step 3: A2UI Extension Module

```python
# a2a-agent/agent/a2ui_extension.py
from a2a.types import AgentExtension


def get_a2ui_agent_extension() -> AgentExtension:
    """Return A2UI extension configuration."""
    return AgentExtension(
        uri="a2ui:agent",
        name="A2UI Support",
        description="Agent can generate A2UI declarative JSON for dynamic UIs",
        version="0.8.0",
    )
```

#### Step 4: Frontend A2UI Integration

```tsx
// src/app/theme.ts
import { v0_8 } from "@a2ui/lit";

// A2UI Theme Configuration
export const a2uiTheme: v0_8.Types.Theme = {
  additionalStyles: {
    Button: {
      "--n-35": "var(--n-100)",
      "--n-30": "var(--n-100)",
    },
  },
  components: {
    Button: {
      "layout-pt-2": true,
      "layout-pb-2": true,
      "layout-pl-4": true,
      "layout-pr-4": true,
      "border-br-12": true,
      "border-bw-0": true,
      "color-bgc-p30": true,
      "color-c-n100": true,
    },
    Card: {
      "border-br-9": true,
      "color-bgc-p100": true,
      "layout-p-4": true,
    },
  },
  elements: {
    body: {
      "typography-f-s": true,
      "typography-fs-n": true,
      "color-c-n10": true,
    },
    button: {
      "typography-f-sf": true,
      "color-bgc-p30": true,
      "color-c-n100": true,
    },
  },
  markdown: {
    p: ["typography-f-s", "typography-fs-n"],
    h1: ["typography-f-s", "typography-sz-tl"],
  },
};
```


#### Step 5: A2UI Page Component

```tsx
// src/app/components/A2UIPage.tsx
"use client";

import { CopilotKitProvider, CopilotSidebar, CopilotPopup } from "@copilotkitnext/react";
import { createA2UIMessageRenderer } from "@copilotkit/a2ui-renderer";
import { a2uiTheme } from "../theme";
import { useMediaQuery } from "@/hooks/use-media-query";

// Create A2UI renderer with custom theme
const A2UIRenderer = createA2UIMessageRenderer({ theme: a2uiTheme });
const activityRenderers = [A2UIRenderer];

interface A2UIPageProps {
  children: React.ReactNode;
}

export function A2UIPage({ children }: A2UIPageProps) {
  const isDesktop = useMediaQuery("(min-width: 768px)");

  return (
    <CopilotKitProvider
      runtimeUrl="/api/copilotkit-a2ui"
      showDevConsole={false}
      renderActivityMessages={activityRenderers}
    >
      {isDesktop ? (
        <>
          {children}
          <CopilotSidebar
            defaultOpen={true}
            labels={{
              modalHeaderTitle: "A2UI Assistant",
              chatInputPlaceholder: "Ask me to generate any UI!",
            }}
          />
        </>
      ) : (
        <>
          {children}
          <CopilotPopup
            defaultOpen={false}
            labels={{
              modalHeaderTitle: "A2UI Assistant",
              chatInputPlaceholder: "Ask me to generate any UI!",
            }}
          />
        </>
      )}
    </CopilotKitProvider>
  );
}
```

#### Step 6: A2UI API Route

```tsx
// src/app/api/copilotkit-a2ui/route.ts
import { NextRequest } from "next/server";
import { CopilotRuntime, OpenAIAdapter } from "@copilotkitnext/runtime";

const copilotKit = new CopilotRuntime({
  remoteEndpoints: [
    {
      url: process.env.A2A_AGENT_URL || "http://localhost:10002",
    },
  ],
});

export async function POST(req: NextRequest) {
  return copilotKit.handleRequest(req);
}
```

#### Step 7: Main Page with Agent Switching

```tsx
// src/app/page.tsx
"use client";

import { useState } from "react";
import { CopilotKitProvider, CopilotSidebar } from "@copilotkitnext/react";
import { A2UIPage } from "./components/A2UIPage";
import { CopilotContextProvider } from "./components/CopilotContextProvider";
import "@copilotkitnext/react/styles.css";

export default function Home() {
  const [activeAgent, setActiveAgent] = useState<"default" | "a2ui">("default");

  if (activeAgent === "a2ui") {
    return (
      <A2UIPage>
        <PageContent
          activeAgent={activeAgent}
          setActiveAgent={setActiveAgent}
        />
      </A2UIPage>
    );
  }

  return (
    <CopilotKitProvider runtimeUrl="/api/copilotkit" showDevConsole={false}>
      <CopilotContextProvider>
        <PageContent
          activeAgent={activeAgent}
          setActiveAgent={setActiveAgent}
        />
        <CopilotSidebar
          defaultOpen={true}
          labels={{
            modalHeaderTitle: "Static + MCP Apps",
            chatInputPlaceholder: "Ask about weather, stocks, or try apps!",
          }}
        />
      </CopilotContextProvider>
    </CopilotKitProvider>
  );
}

function PageContent({
  activeAgent,
  setActiveAgent,
}: {
  activeAgent: "default" | "a2ui";
  setActiveAgent: (agent: "default" | "a2ui") => void;
}) {
  return (
    <main className="p-8">
      <h1 className="text-3xl font-bold mb-6">Generative UI Demo</h1>
      
      <div className="flex gap-4 mb-8">
        <button
          onClick={() => setActiveAgent("default")}
          className={`px-4 py-2 rounded ${
            activeAgent === "default" ? "bg-blue-500 text-white" : "bg-gray-200"
          }`}
        >
          Static + MCP Apps
        </button>
        <button
          onClick={() => setActiveAgent("a2ui")}
          className={`px-4 py-2 rounded ${
            activeAgent === "a2ui" ? "bg-blue-500 text-white" : "bg-gray-200"
          }`}
        >
          A2UI
        </button>
      </div>

      {activeAgent === "default" ? (
        <div>
          <h2 className="text-xl mb-4">Try these prompts:</h2>
          <ul className="list-disc ml-6 space-y-2">
            <li>"What's the weather in Tokyo?"</li>
            <li>"Get stock price for AAPL"</li>
            <li>"Open the calculator"</li>
          </ul>
        </div>
      ) : (
        <div>
          <h2 className="text-xl mb-4">A2UI Prompts:</h2>
          <ul className="list-disc ml-6 space-y-2">
            <li>"Create a contact form"</li>
            <li>"Show me a todo list"</li>
            <li>"Make a profile card for John Doe"</li>
          </ul>
        </div>
      )}
    </main>
  );
}
```

---

## 5. Complete Project Setup

### 5.1 Project Structure

```
generative-ui-demo/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── copilotkit/
│   │   │   │   └── route.ts
│   │   │   └── copilotkit-a2ui/
│   │   │       └── route.ts
│   │   ├── components/
│   │   │   ├── A2UIPage.tsx
│   │   │   ├── CopilotContextProvider.tsx
│   │   │   └── static-tools/
│   │   │       ├── WeatherCard.tsx
│   │   │       └── TaskApprovalCard.tsx
│   │   ├── page.tsx
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   └── theme.ts
│   └── hooks/
│       └── use-media-query.ts
├── mcp-server/
│   ├── server.ts
│   ├── src/
│   │   ├── calculator.ts
│   │   └── flights.ts
│   └── apps/
│       ├── calculator.html
│       └── flights.html
├── a2a-agent/
│   └── agent/
│       ├── __main__.py
│       ├── agent.py
│       ├── a2ui_extension.py
│       └── prompt_builder.py
├── package.json
├── tsconfig.json
└── .env
```

### 5.2 Installation Commands

```bash
# Clone and install dependencies
npm install

# Install MCP server dependencies
cd mcp-server
npm install
cd ..

# Install Python A2A agent dependencies
cd a2a-agent
pip install -e .
cd ..
```

### 5.3 Running the Application

```bash
# Terminal 1: MCP Server (port 3001)
cd mcp-server && npm run dev

# Terminal 2: Python A2A Agent (port 10002)
cd a2a-agent && python -m agent

# Terminal 3: Next.js Frontend (port 3000)
npm run dev
```


### 5.4 Package.json

```json
{
  "name": "generative-ui-demo",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint"
  },
  "dependencies": {
    "@a2ui/lit": "^0.8.1",
    "@ag-ui/a2a": "^0.0.6",
    "@ag-ui/mcp-apps-middleware": "^0.0.1",
    "@copilotkit/a2ui-renderer": "^0.0.2",
    "@copilotkitnext/react": "1.51.0-next.4",
    "@copilotkitnext/runtime": "^1.51.0-next.4",
    "next": "16.1.3",
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "zod": "^3.25.76"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.1.3",
    "tailwindcss": "^4",
    "typescript": "^5"
  }
}
```

### 5.5 Python Requirements

```txt
# a2a-agent/requirements.txt
a2a-sdk>=0.2.5
google-adk>=0.1.0
litellm>=1.0.0
jsonschema>=4.0.0
click>=8.0.0
uvicorn>=0.24.0
python-dotenv>=1.0.0
```

```python
# a2a-agent/setup.py
from setuptools import setup, find_packages

setup(
    name="a2a-agent",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "a2a-sdk>=0.2.5",
        "google-adk>=0.1.0",
        "litellm>=1.0.0",
        "jsonschema>=4.0.0",
        "click>=8.0.0",
        "uvicorn>=0.24.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "a2a-agent=agent.__main__:main",
        ],
    },
)
```

---

## 6. Best Practices & Tips

### 6.1 Static GenUI Best Practices

1. **Loading States**: Always provide loading states for better UX
   ```tsx
   render: ({ status }) => {
     if (status === "inProgress") {
       return <LoadingState />;
     }
     // ...
   }
   ```

2. **Result Parsing**: Parse JSON results from strings
   ```tsx
   const data = JSON.parse(result) as WeatherData;
   ```

3. **Error Handling**: Handle error states gracefully
   ```tsx
   if (status === "complete" && !result) {
     return <ErrorCard message="Failed to load data" />;
   }
   ```

4. **Type Safety**: Use Zod schemas for parameters
   ```tsx
   parameters: z.object({
     location: z.string().describe("City name"),
   })
   ```

### 6.2 MCP Apps Best Practices

1. **Session Management**: Store session state server-side
   ```typescript
   const activeSessions: Map<string, SessionState> = new Map();
   ```

2. **Resource Linking**: Always link tools to their UI resources
   ```typescript
   _meta: {
     [RESOURCE_URI_META_KEY]: resource.uri,
   }
   ```

3. **Error Responses**: Return structured error content
   ```typescript
   return {
     content: [{ type: "text", text: "Error message" }],
     structuredContent: { success: false, error: "Details" },
   };
   ```

4. **CORS Configuration**: Allow cross-origin requests
   ```typescript
   app.use(cors({ origin: "*", exposedHeaders: ["Mcp-Session-Id"] }));
   ```

### 6.3 A2UI Best Practices

1. **Schema Validation**: Always validate A2UI JSON
   ```python
   jsonschema.validate(instance=parsed_json, schema=a2ui_schema)
   ```

2. **Response Delimiter**: Use delimiter for JSON extraction
   ```
   <text>---a2ui_JSON---<json>
   ```

3. **Theme Consistency**: Match A2UI theme with app design
   ```tsx
   const a2uiTheme: v0_8.Types.Theme = {
     components: { /* ... */ },
     elements: { /* ... */ },
   };
   ```

4. **Agent Card Extensions**: Include A2UI capability
   ```python
   capabilities=AgentCapabilities(
       extensions=[get_a2ui_agent_extension()],
   )
   ```

### 6.4 Comparison Table

| Feature | Static GenUI | MCP Apps | A2UI |
|---------|--------------|----------|------|
| **Complexity** | Low | Medium | High |
| **Interactivity** | Medium | High | High |
| **Flexibility** | Low | Medium | Very High |
| **Server Required** | No | Yes | Yes |
| **Use Case** | Simple displays | Rich apps | Dynamic generation |
| **Learning Curve** | Low | Medium | High |

### 6.5 When to Use Each

- **Static GenUI**: Weather cards, stock tickers, simple approvals
- **MCP Apps**: Booking wizards, calculators, trading simulators
- **A2UI**: Form builders, dynamic lists, custom dashboards

---

## References

- [CopilotKit Documentation](https://docs.copilotkit.ai)
- [Generative UI Types](https://www.copilotkit.ai/generative-ui)
- [A2UI Specification](https://a2ui.org)
- [MCP Protocol](https://modelcontextprotocol.io)
- [A2A Protocol](https://a2a.org)

---

*Document generated based on analysis of the CopilotKit generative-ui-playground repository.*
