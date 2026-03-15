"use client";

import { LayoutGrid, List, Upload, Search } from "lucide-react";

interface ToolbarProps {
  viewMode: "grid" | "list";
  onViewChange: (mode: "grid" | "list") => void;
  onUploadClick: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export function Toolbar({
  viewMode,
  onViewChange,
  onUploadClick,
  searchQuery,
  onSearchChange,
}: ToolbarProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-200">
      {/* Upload button */}
      <button
        type="button"
        onClick={onUploadClick}
        className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
      >
        <Upload size={15} />
        Upload
      </button>

      {/* Search input */}
      <div className="relative flex-1 max-w-xs">
        <Search
          size={15}
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
        />
        <input
          type="text"
          placeholder="Search files..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* View toggle */}
      <div className="flex items-center border border-gray-300 rounded-md overflow-hidden">
        <button
          type="button"
          onClick={() => onViewChange("grid")}
          title="Grid view"
          className={`p-1.5 transition-colors ${
            viewMode === "grid"
              ? "bg-gray-200 text-gray-900"
              : "text-gray-500 hover:bg-gray-100"
          }`}
        >
          <LayoutGrid size={16} />
        </button>
        <button
          type="button"
          onClick={() => onViewChange("list")}
          title="List view"
          className={`p-1.5 transition-colors ${
            viewMode === "list"
              ? "bg-gray-200 text-gray-900"
              : "text-gray-500 hover:bg-gray-100"
          }`}
        >
          <List size={16} />
        </button>
      </div>
    </div>
  );
}
