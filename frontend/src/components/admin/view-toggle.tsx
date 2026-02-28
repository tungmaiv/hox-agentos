"use client";
/**
 * ViewToggle — toggle between table and card grid view modes.
 *
 * Stores the user's preference in localStorage under "admin-view-mode"
 * so it persists across page navigations and sessions.
 */
import { useState, useEffect } from "react";
import type { ViewMode } from "@/lib/admin-types";

const STORAGE_KEY = "admin-view-mode";

interface ViewToggleProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
}

export function ViewToggle({ value, onChange }: ViewToggleProps) {
  return (
    <div className="inline-flex rounded-md border border-gray-300 bg-white">
      <button
        className={`px-3 py-1.5 text-xs font-medium rounded-l-md transition-colors ${
          value === "table"
            ? "bg-blue-600 text-white"
            : "text-gray-600 hover:bg-gray-50"
        }`}
        onClick={() => onChange("table")}
        aria-label="Table view"
      >
        Table
      </button>
      <button
        className={`px-3 py-1.5 text-xs font-medium rounded-r-md transition-colors ${
          value === "cards"
            ? "bg-blue-600 text-white"
            : "text-gray-600 hover:bg-gray-50"
        }`}
        onClick={() => onChange("cards")}
        aria-label="Card grid view"
      >
        Cards
      </button>
    </div>
  );
}

/** Hook to persist and restore view mode preference. */
export function useViewMode(): [ViewMode, (mode: ViewMode) => void] {
  const [mode, setMode] = useState<ViewMode>("table");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "table" || stored === "cards") {
      setMode(stored);
    }
  }, []);

  const setAndStore = (newMode: ViewMode) => {
    setMode(newMode);
    localStorage.setItem(STORAGE_KEY, newMode);
  };

  return [mode, setAndStore];
}
