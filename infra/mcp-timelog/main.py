"""
Mock Timelog MCP server implementing MCP JSON-RPC spec.

POST /sse — accepts tools/list and tools/call JSON-RPC requests.
Returns JSON response directly (not SSE stream — sufficient for mock).

Tools exposed:
  timelog.get_entries      — get time entries for a date range
  timelog.add_entry        — add a new time entry
  timelog.get_summary      — get daily/weekly time summary
  timelog.update_entry     — update an existing time entry
"""

from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta

app = FastAPI(title="Blitz Timelog Mock MCP Server")

# Mock time entries database
MOCK_ENTRIES: list[dict[str, Any]] = [
    {
        "id": "TE-001",
        "date": "2026-03-03",
        "project": "Project Alpha",
        "task": "Implement auth",
        "hours": 4.0,
        "description": "Completed OAuth integration",
    },
    {
        "id": "TE-002",
        "date": "2026-03-03",
        "project": "Project Alpha",
        "task": "Memory layer",
        "hours": 3.5,
        "description": "Started vector storage implementation",
    },
    {
        "id": "TE-003",
        "date": "2026-03-02",
        "project": "Project Beta",
        "task": "API design",
        "hours": 6.0,
        "description": "Reviewed OpenAPI specs",
    },
]

TOOLS = [
    {
        "name": "get_entries",
        "description": "Get time entries for a date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Start date (YYYY-MM-DD)",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "End date (YYYY-MM-DD)",
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project name (optional)",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "add_entry",
        "description": "Add a new time entry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "Date (YYYY-MM-DD)",
                },
                "project": {"type": "string", "description": "Project name"},
                "task": {"type": "string", "description": "Task name"},
                "hours": {"type": "number", "description": "Hours worked"},
                "description": {"type": "string", "description": "Work description"},
            },
            "required": ["date", "project", "hours"],
        },
    },
    {
        "name": "get_summary",
        "description": "Get daily or weekly time summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "Date for daily summary (YYYY-MM-DD)",
                },
                "week_start": {
                    "type": "string",
                    "format": "date",
                    "description": "Week start date for weekly summary (YYYY-MM-DD)",
                },
            },
        },
    },
    {
        "name": "update_entry",
        "description": "Update an existing time entry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "Entry ID to update"},
                "hours": {"type": "number", "description": "New hours value"},
                "description": {"type": "string", "description": "New description"},
            },
            "required": ["entry_id"],
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

        if tool_name == "get_entries":
            start_date = arguments.get("start_date", "")
            end_date = arguments.get("end_date", "")
            project_filter = arguments.get("project")

            filtered = [
                entry
                for entry in MOCK_ENTRIES
                if start_date <= entry["date"] <= end_date
                and (not project_filter or entry["project"] == project_filter)
            ]
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "entries": filtered,
                        "total_hours": sum(e["hours"] for e in filtered),
                    },
                }
            )

        if tool_name == "add_entry":
            new_id = f"TE-{len(MOCK_ENTRIES) + 1:03d}"
            new_entry = {
                "id": new_id,
                "date": arguments.get("date"),
                "project": arguments.get("project"),
                "task": arguments.get("task", ""),
                "hours": arguments.get("hours", 0),
                "description": arguments.get("description", ""),
            }
            MOCK_ENTRIES.append(new_entry)
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"entry": new_entry, "success": True},
                }
            )

        if tool_name == "get_summary":
            date = arguments.get("date")
            week_start = arguments.get("week_start")

            if date:
                # Daily summary
                day_entries = [e for e in MOCK_ENTRIES if e["date"] == date]
                total = sum(e["hours"] for e in day_entries)
                by_project = {}
                for e in day_entries:
                    by_project[e["project"]] = (
                        by_project.get(e["project"], 0) + e["hours"]
                    )

                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "type": "daily",
                            "date": date,
                            "total_hours": total,
                            "by_project": by_project,
                            "entries_count": len(day_entries),
                        },
                    }
                )

            elif week_start:
                # Weekly summary
                start = datetime.strptime(week_start, "%Y-%m-%d")
                end = start + timedelta(days=6)
                week_entries = [
                    e
                    for e in MOCK_ENTRIES
                    if start <= datetime.strptime(e["date"], "%Y-%m-%d") <= end
                ]
                total = sum(e["hours"] for e in week_entries)
                by_project = {}
                for e in week_entries:
                    by_project[e["project"]] = (
                        by_project.get(e["project"], 0) + e["hours"]
                    )

                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "type": "weekly",
                            "week_start": week_start,
                            "week_end": end.strftime("%Y-%m-%d"),
                            "total_hours": total,
                            "by_project": by_project,
                            "entries_count": len(week_entries),
                        },
                    }
                )

            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": "Either 'date' or 'week_start' must be provided",
                    },
                }
            )

        if tool_name == "update_entry":
            entry_id = arguments.get("entry_id")
            entry = next((e for e in MOCK_ENTRIES if e["id"] == entry_id), None)

            if entry is None:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": f"Entry '{entry_id}' not found",
                        },
                    }
                )

            if "hours" in arguments:
                entry["hours"] = arguments["hours"]
            if "description" in arguments:
                entry["description"] = arguments["description"]

            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"entry": entry, "success": True},
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
    uvicorn.run(app, host="0.0.0.0", port=8002)
