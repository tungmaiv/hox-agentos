"use client";
/**
 * NodePalette — left sidebar listing draggable node types.
 *
 * Node types available for drag-and-drop onto the workflow canvas.
 * Drag-and-drop wiring comes in plan 04-04. For now this is a visual
 * placeholder listing the 6 supported node categories.
 */

interface NodeType {
  id: string;
  label: string;
  description: string;
  icon: string;
}

const NODE_TYPES: NodeType[] = [
  {
    id: "trigger",
    label: "Trigger",
    description: "Start a workflow (schedule, webhook, manual)",
    icon: "T",
  },
  {
    id: "agent",
    label: "Agent",
    description: "Run an AI agent sub-task",
    icon: "A",
  },
  {
    id: "tool",
    label: "Tool",
    description: "Call a registered tool (email, calendar, etc.)",
    icon: "R",
  },
  {
    id: "condition",
    label: "Condition",
    description: "Branch workflow on a boolean condition",
    icon: "C",
  },
  {
    id: "hitl",
    label: "Human Review",
    description: "Pause and wait for human approval",
    icon: "H",
  },
  {
    id: "output",
    label: "Output",
    description: "Deliver results (chat, email, channel)",
    icon: "O",
  },
];

export function NodePalette() {
  return (
    <div className="w-56 h-full border-r bg-white flex flex-col">
      <div className="px-3 py-2 border-b">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Node Types
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {NODE_TYPES.map((node) => (
          <div
            key={node.id}
            draggable
            className="flex items-start gap-2 p-2 rounded-md border border-gray-200 bg-gray-50 cursor-grab hover:border-blue-400 hover:bg-blue-50 transition-colors"
          >
            <span className="flex-shrink-0 w-6 h-6 rounded bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center">
              {node.icon}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-700 leading-tight">
                {node.label}
              </p>
              <p className="text-xs text-gray-400 leading-tight mt-0.5">
                {node.description}
              </p>
            </div>
          </div>
        ))}
      </div>
      <div className="px-3 py-2 border-t text-xs text-gray-400">
        Drag onto canvas to add
      </div>
    </div>
  );
}
