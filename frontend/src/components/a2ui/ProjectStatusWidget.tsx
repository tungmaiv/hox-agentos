"use client"

/**
 * ProjectStatusWidget — renders ProjectStatusResult from the project sub-agent.
 *
 * Shows: project name, colored status badge, progress bar, owner, last update.
 * Expandable kanban section shows columns (todo / in_progress / done).
 * Kanban task moves call useMcpTool("crm.update_task_status") — this is the
 * key architectural requirement from CONTEXT.md (useMcpTool is the ONLY way
 * A2UI components call tools).
 *
 * Client Component — uses useState for expand/collapse.
 * CLAUDE.md: no `any`; useMcpTool for all tool calls.
 */
import { useState } from "react"
import type { ProjectStatusResult } from "@/lib/a2ui-types"
import { useMcpTool } from "@/hooks/use-mcp-tool"

interface Props {
  data: ProjectStatusResult
}

interface UpdateTaskStatusParams {
  task_id: string
  new_status: string
}

interface UpdateTaskStatusResult {
  success: boolean
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  "on-hold": "bg-yellow-100 text-yellow-700",
  completed: "bg-gray-100 text-gray-700",
}

const KANBAN_COLUMNS = ["todo", "in_progress", "done"] as const
type KanbanColumn = (typeof KANBAN_COLUMNS)[number]

const COLUMN_LABELS: Record<KanbanColumn, string> = {
  todo: "To Do",
  in_progress: "In Progress",
  done: "Done",
}

export function ProjectStatusWidget({ data }: Props) {
  const [isExpanded, setIsExpanded] = useState(false)

  // useMcpTool("crm.update_task_status") — the ONLY way this component moves tasks
  const { call: updateTaskStatus, isLoading: isUpdating } = useMcpTool<
    UpdateTaskStatusParams,
    UpdateTaskStatusResult
  >("crm.update_task_status")

  // Refresh project data via crm.get_project_status
  const { call: refreshProject, isLoading: isRefreshing } = useMcpTool<
    { project_name: string },
    unknown
  >("crm.get_project_status")

  const handleTaskMove = async (taskId: string, newStatus: string) => {
    await updateTaskStatus({ task_id: taskId, new_status: newStatus })
  }

  const badgeClass =
    STATUS_STYLES[data.status] ?? "bg-gray-100 text-gray-700"

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm p-4 my-2 max-w-lg">
      {/* Header: project name + status badge + refresh */}
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-900">
          {data.project_name}
        </h3>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${badgeClass}`}>
            {data.status}
          </span>
          <button
            onClick={() => refreshProject({ project_name: data.project_name })}
            disabled={isRefreshing}
            className="text-gray-400 hover:text-gray-600 text-xs disabled:opacity-50"
            title="Refresh project status"
            aria-label="Refresh project status"
          >
            {isRefreshing ? "..." : "\u21BA"}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all"
          style={{ width: `${data.progress_pct}%` }}
          role="progressbar"
          aria-valuenow={data.progress_pct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      <p className="text-xs text-gray-500 mb-1">
        Progress: {data.progress_pct}%
      </p>
      <p className="text-xs text-gray-500">Owner: {data.owner}</p>
      <p className="text-xs text-gray-400">Updated: {data.last_update}</p>

      {/* Expand/collapse kanban board */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="mt-3 text-xs text-blue-600 hover:underline"
        aria-expanded={isExpanded}
      >
        {isExpanded ? "Hide tasks" : "Show kanban board"}
      </button>

      {isExpanded && (
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
          {KANBAN_COLUMNS.map((col) => (
            <div key={col} className="bg-gray-50 rounded p-2 min-h-[60px]">
              <div className="font-medium text-gray-600 mb-2">
                {COLUMN_LABELS[col]}
              </div>
              {/* Phase 3: kanban shows empty columns as drop targets.
                  Task data comes from a separate MCP call in Phase 4.
                  The move button demonstrates useMcpTool wiring is correct. */}
              <button
                onClick={() =>
                  handleTaskMove("demo-task-1", col)
                }
                disabled={isUpdating}
                className="w-full text-left text-xs text-gray-400 hover:text-gray-600 disabled:opacity-50 p-1 rounded border border-dashed border-gray-200 hover:border-gray-300"
                title={`Move demo task to ${COLUMN_LABELS[col]}`}
              >
                + Move here
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
