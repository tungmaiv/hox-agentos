"use client";

import { useState } from "react";
import { FileText, Image as ImageIcon, File, Brain, MoreHorizontal } from "lucide-react";
import type { StorageFile } from "../types";
import { EXTRACTABLE_MIME_TYPES, formatFileSize, formatRelativeTime } from "../types";

interface FileActionMenuProps {
  file: StorageFile;
  onAction: (action: string, file: StorageFile) => void;
  onClose: () => void;
  openUpward?: boolean;
}

function FileActionMenu({ file, onAction, onClose, openUpward }: FileActionMenuProps) {
  const canAddToMemory = EXTRACTABLE_MIME_TYPES.has(file.mime_type);

  return (
    <div className={`absolute right-0 z-30 bg-white border border-gray-200 rounded-lg shadow-xl py-1 w-44 ${openUpward ? "bottom-8" : "top-8"}`}>
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
  );
}

function fileIcon(mimeType: string): React.ReactNode {
  if (mimeType.startsWith("image/")) return <ImageIcon size={16} className="text-green-500" />;
  if (
    mimeType === "application/pdf" ||
    mimeType.includes("wordprocessingml") ||
    mimeType.includes("text")
  ) return <FileText size={16} className="text-blue-500" />;
  return <File size={16} className="text-gray-400" />;
}

interface FileListProps {
  files: StorageFile[];
  onAction: (action: string, file: StorageFile) => void;
}

export function FileList({ files, onAction }: FileListProps) {
  const [menuFile, setMenuFile] = useState<{ id: string; upward: boolean } | null>(null);

  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-gray-400 text-sm">
        <File size={40} className="mb-2 opacity-30" />
        No files here yet
      </div>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-gray-200 text-left text-xs text-gray-500 uppercase tracking-wide">
          <th className="px-4 py-2 font-medium">Name</th>
          <th className="px-4 py-2 font-medium">Size</th>
          <th className="px-4 py-2 font-medium">Modified</th>
          <th className="px-4 py-2 font-medium">Owner</th>
          <th className="px-4 py-2 w-8" />
        </tr>
      </thead>
      <tbody>
        {files.map((file) => (
          <tr
            key={file.id}
            className="border-b border-gray-100 hover:bg-gray-50 transition-colors group"
          >
            {/* Name */}
            <td className="px-4 py-2">
              <div className="flex items-center gap-2">
                {fileIcon(file.mime_type)}
                <span className="truncate max-w-xs">{file.name}</span>
                {file.in_memory && (
                  <span title="In your long-term memory" className="text-purple-500 shrink-0">
                    <Brain size={13} />
                  </span>
                )}
              </div>
            </td>
            {/* Size */}
            <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
              {formatFileSize(file.size_bytes)}
            </td>
            {/* Modified */}
            <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
              {formatRelativeTime(file.updated_at)}
            </td>
            {/* Owner */}
            <td className="px-4 py-2 text-gray-500 truncate max-w-[8rem]">
              {file.owner_user_id}
            </td>
            {/* Actions */}
            <td className="px-4 py-2 relative">
              <button
                type="button"
                title="More actions"
                onClick={(e) => {
                  e.stopPropagation();
                  if (menuFile?.id === file.id) { setMenuFile(null); return; }
                  const rect = e.currentTarget.getBoundingClientRect();
                  const upward = window.innerHeight - rect.bottom < 160;
                  setMenuFile({ id: file.id, upward });
                }}
                className="opacity-0 group-hover:opacity-100 p-0.5 text-gray-400 hover:text-gray-700 rounded transition-opacity"
              >
                <MoreHorizontal size={15} />
              </button>
              {menuFile?.id === file.id && (
                <FileActionMenu
                  file={file}
                  onAction={onAction}
                  onClose={() => setMenuFile(null)}
                  openUpward={menuFile.upward}
                />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
