"use client";

import { useState } from "react";
import { FileText, Image as ImageIcon, File, Brain, MoreHorizontal } from "lucide-react";
import type { StorageFile } from "../types";
import { EXTRACTABLE_MIME_TYPES } from "../types";

const MENU_HEIGHT = 160;
const MENU_WIDTH = 176; // w-44

interface FileActionMenuProps {
  file: StorageFile;
  onAction: (action: string, file: StorageFile) => void;
  onClose: () => void;
  style: React.CSSProperties;
}

function FileActionMenu({ file, onAction, onClose, style }: FileActionMenuProps) {
  const canAddToMemory = EXTRACTABLE_MIME_TYPES.has(file.mime_type);

  return (
    <>
      <div className="fixed inset-0 z-[39]" onClick={onClose} />
      <div
        style={style}
        className="fixed z-40 bg-white border border-gray-200 rounded-lg shadow-xl py-1 w-44"
      >
        <button
          type="button"
          className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 transition-colors"
          onClick={() => { onAction("download", file); onClose(); }}
        >
          Download
        </button>
        <button
          type="button"
          className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 transition-colors"
          onClick={() => { onAction("share", file); onClose(); }}
        >
          Share
        </button>
        <button
          type="button"
          disabled={!canAddToMemory}
          title={!canAddToMemory ? "File type not supported for memory indexing" : undefined}
          className={`w-full text-left px-3 py-1.5 text-sm transition-colors ${
            canAddToMemory
              ? "hover:bg-gray-50"
              : "text-gray-400 cursor-not-allowed"
          }`}
          onClick={() => {
            if (canAddToMemory) { onAction("add-to-memory", file); onClose(); }
          }}
        >
          Add to Memory
        </button>
        <div className="border-t border-gray-100 my-1" />
        <button
          type="button"
          className="w-full text-left px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
          onClick={() => { onAction("delete", file); onClose(); }}
        >
          Delete
        </button>
      </div>
    </>
  );
}

function fileIcon(mimeType: string): React.ReactNode {
  if (mimeType.startsWith("image/")) return <ImageIcon size={36} className="text-green-500" />;
  if (
    mimeType === "application/pdf" ||
    mimeType.includes("wordprocessingml") ||
    mimeType.includes("text")
  ) return <FileText size={36} className="text-blue-500" />;
  return <File size={36} className="text-gray-400" />;
}

interface FileGridProps {
  files: StorageFile[];
  onAction: (action: string, file: StorageFile) => void;
}

interface MenuState {
  id: string;
  top: number;
  left: number;
}

export function FileGrid({ files, onAction }: FileGridProps) {
  const [menuState, setMenuState] = useState<MenuState | null>(null);

  function openMenu(e: React.MouseEvent<HTMLButtonElement>, file: StorageFile) {
    e.stopPropagation();
    if (menuState?.id === file.id) { setMenuState(null); return; }
    const rect = e.currentTarget.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const top = spaceBelow >= MENU_HEIGHT ? rect.bottom + 4 : rect.top - MENU_HEIGHT - 4;
    const left = Math.min(rect.left, window.innerWidth - MENU_WIDTH - 4);
    setMenuState({ id: file.id, top, left });
  }

  function handleContextMenu(e: React.MouseEvent, file: StorageFile) {
    e.preventDefault();
    const spaceBelow = window.innerHeight - e.clientY;
    const top = spaceBelow >= MENU_HEIGHT ? e.clientY : e.clientY - MENU_HEIGHT;
    const left = Math.min(e.clientX, window.innerWidth - MENU_WIDTH - 4);
    setMenuState({ id: file.id, top, left });
  }

  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-gray-400 text-sm">
        <File size={40} className="mb-2 opacity-30" />
        No files here yet
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 p-4">
        {files.map((file) => (
          <div
            key={file.id}
            className="group relative flex flex-col items-center gap-2 p-2 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
            onContextMenu={(e) => handleContextMenu(e, file)}
          >
            {/* Icon area */}
            <div className="relative w-20 h-20 flex items-center justify-center">
              {fileIcon(file.mime_type)}
              {file.in_memory && (
                <span
                  title="In your long-term memory"
                  className="absolute bottom-0 right-0 text-purple-500"
                >
                  <Brain size={14} />
                </span>
              )}
            </div>

            {/* Filename */}
            <span className="text-xs text-center text-gray-700 line-clamp-2 w-full">
              {file.name}
            </span>

            {/* ... menu button — visible on hover */}
            <button
              type="button"
              title="More actions"
              onClick={(e) => openMenu(e, file)}
              className="absolute top-1 right-1 p-0.5 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-gray-900 transition-opacity rounded"
            >
              <MoreHorizontal size={15} />
            </button>
          </div>
        ))}
      </div>

      {menuState && (
        <FileActionMenu
          file={files.find((f) => f.id === menuState.id)!}
          onAction={onAction}
          onClose={() => setMenuState(null)}
          style={{ top: menuState.top, left: menuState.left }}
        />
      )}
    </>
  );
}
