"use client";

import type { DragEvent } from "react";

interface PaletteItem {
  type: string;
  label: string;
  icon: string;
  color: string;
}

const PALETTE: PaletteItem[] = [
  {
    type: "trigger_node",
    label: "Trigger",
    icon: "T",
    color:
      "bg-orange-50 border-orange-200 hover:border-orange-400",
  },
  {
    type: "agent_node",
    label: "Agent",
    icon: "A",
    color: "bg-blue-50 border-blue-200 hover:border-blue-400",
  },
  {
    type: "tool_node",
    label: "Tool",
    icon: "R",
    color: "bg-gray-50 border-gray-200 hover:border-gray-400",
  },
  {
    type: "condition_node",
    label: "Condition",
    icon: "C",
    color:
      "bg-purple-50 border-purple-200 hover:border-purple-400",
  },
  {
    type: "hitl_approval_node",
    label: "Approval",
    icon: "H",
    color:
      "bg-yellow-50 border-yellow-200 hover:border-yellow-400",
  },
  {
    type: "channel_output_node",
    label: "Send",
    icon: "O",
    color: "bg-green-50 border-green-200 hover:border-green-400",
  },
];

function onDragStart(e: DragEvent<HTMLDivElement>, nodeType: string) {
  e.dataTransfer.setData("application/reactflow", nodeType);
  e.dataTransfer.effectAllowed = "move";
}

export function NodePalette() {
  return (
    <div className="w-44 border-r border-gray-100 bg-white p-3 flex flex-col gap-2 overflow-y-auto shrink-0">
      <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">
        Nodes
      </h3>
      {PALETTE.map((item) => (
        <div
          key={item.type}
          draggable
          onDragStart={(e) => onDragStart(e, item.type)}
          className={`flex items-center gap-2 px-2 py-2 rounded border cursor-grab active:cursor-grabbing select-none transition-colors ${item.color}`}
        >
          <span className="flex-shrink-0 w-6 h-6 rounded bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center">
            {item.icon}
          </span>
          <span className="text-xs font-medium text-gray-700">{item.label}</span>
        </div>
      ))}
      <div className="mt-auto pt-2 text-[10px] text-gray-400">
        Drag onto canvas to add
      </div>
    </div>
  );
}
