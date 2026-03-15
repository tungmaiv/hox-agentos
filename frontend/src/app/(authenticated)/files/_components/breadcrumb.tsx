"use client";

import { ChevronRight } from "lucide-react";
import type { StorageFolder } from "../types";

interface BreadcrumbProps {
  path: StorageFolder[];
  onNavigate: (folderId: string | null) => void;
}

export function Breadcrumb({ path, onNavigate }: BreadcrumbProps) {
  return (
    <nav
      aria-label="File navigation breadcrumb"
      className="flex items-center gap-1 text-sm text-gray-600 px-4 py-2"
    >
      <button
        type="button"
        onClick={() => onNavigate(null)}
        className={`hover:text-blue-600 transition-colors ${
          path.length === 0 ? "font-semibold text-gray-900 cursor-default" : ""
        }`}
        disabled={path.length === 0}
      >
        My Files
      </button>

      {path.map((folder, idx) => {
        const isLast = idx === path.length - 1;
        return (
          <span key={folder.id} className="flex items-center gap-1">
            <ChevronRight size={14} className="text-gray-400 shrink-0" />
            {isLast ? (
              <span className="font-semibold text-gray-900">{folder.name}</span>
            ) : (
              <button
                type="button"
                onClick={() => onNavigate(folder.id)}
                className="hover:text-blue-600 transition-colors"
              >
                {folder.name}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}
