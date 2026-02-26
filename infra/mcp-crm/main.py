"""
Mock CRM MCP server implementing MCP JSON-RPC spec.

POST /sse — accepts tools/list and tools/call JSON-RPC requests.
Returns JSON response directly (not SSE stream — sufficient for mock).

Tools exposed:
  crm.get_project_status  — get status, progress, tasks for a named project
  crm.list_projects       — list all projects with name, status, owner
  crm.update_task_status  — update kanban task status (used by ProjectStatusWidget)
"""
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Blitz CRM Mock MCP Server")

MOCK_PROJECTS: dict[str, dict[str, Any]] = {
    "Project Alpha": {
        "status": "active",
        "owner": "tung@blitz.local",
        "progress_pct": 65,
        "last_update": "2026-02-25",
        "tasks": [
            {"id": "T-001", "title": "Implement auth", "status": "done"},
            {"id": "T-002", "title": "Memory layer", "status": "in_progress"},
            {"id": "T-003", "title": "MCP integration", "status": "todo"},
        ],
    },
    "Project Beta": {
        "status": "on-hold",
        "owner": "admin@blitz.local",
        "progress_pct": 30,
        "last_update": "2026-02-10",
        "tasks": [],
    },
    "Project Gamma": {
        "status": "completed",
        "owner": "tung@blitz.local",
        "progress_pct": 100,
        "last_update": "2026-01-15",
        "tasks": [],
    },
}

TOOLS = [
    {
        "name": "get_project_status",
        "description": "Get status, progress, and tasks for a named project.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_name": {"type": "string"}},
            "required": ["project_name"],
        },
    },
    {
        "name": "list_projects",
        "description": "List all projects with name, status, and owner.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "update_task_status",
        "description": "Update task status (for kanban drag-drop).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "new_status": {
                    "type": "string",
                    "enum": ["todo", "in_progress", "done"],
                },
            },
            "required": ["task_id", "new_status"],
        },
    },
]


@app.post("/sse")
async def handle_mcp(request: Request) -> JSONResponse:
    body = await request.json()
    method = body.get("method")
    req_id = body.get("id", 1)

    if method == "tools/list":
        return JSONResponse(
            {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
        )

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "get_project_status":
            project_name = arguments.get("project_name", "")
            project = MOCK_PROJECTS.get(project_name)
            if project is None:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": f"Project '{project_name}' not found",
                        },
                    }
                )
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"project_name": project_name, **project},
                }
            )

        if tool_name == "list_projects":
            projects = [
                {"name": name, "status": p["status"], "owner": p["owner"]}
                for name, p in MOCK_PROJECTS.items()
            ]
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"projects": projects},
                }
            )

        if tool_name == "update_task_status":
            task_id = arguments.get("task_id")
            new_status = arguments.get("new_status")
            for project in MOCK_PROJECTS.values():
                for task in project.get("tasks", []):
                    if task["id"] == task_id:
                        task["status"] = new_status
                        return JSONResponse(
                            {
                                "jsonrpc": "2.0",
                                "id": req_id,
                                "result": {
                                    "task_id": task_id,
                                    "new_status": new_status,
                                    "success": True,
                                },
                            }
                        )
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": f"Task '{task_id}' not found",
                    },
                }
            )

        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        )

    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
