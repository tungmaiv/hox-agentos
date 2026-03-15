"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronRight, ChevronDown, Folder, FolderOpen, Plus } from "lucide-react";
import type { StorageFolder } from "../types";

interface FolderNodeProps {
  folder: StorageFolder;
  allFolders: StorageFolder[];
  currentFolderId: string | null;
  onSelectFolder: (id: string | null) => void;
}

function FolderNode({
  folder,
  allFolders,
  currentFolderId,
  onSelectFolder,
}: FolderNodeProps) {
  const children = allFolders.filter(
    (f) => f.parent_folder_id === folder.id
  );
  const [expanded, setExpanded] = useState(false);
  const isSelected = currentFolderId === folder.id;

  return (
    <li>
      <button
        type="button"
        onClick={() => {
          onSelectFolder(folder.id);
          if (children.length > 0) setExpanded((prev) => !prev);
        }}
        className={`w-full flex items-center gap-1 px-2 py-1.5 text-sm rounded-md transition-colors ${
          isSelected
            ? "bg-primary/10 text-blue-700 font-medium"
            : "text-gray-700 hover:bg-gray-100"
        }`}
      >
        {children.length > 0 ? (
          <span className="shrink-0 text-gray-400">
            {expanded ? (
              <ChevronDown size={14} />
            ) : (
              <ChevronRight size={14} />
            )}
          </span>
        ) : (
          <span className="w-3.5 shrink-0" />
        )}
        {isSelected ? (
          <FolderOpen size={15} className="shrink-0 text-blue-500" />
        ) : (
          <Folder size={15} className="shrink-0 text-yellow-500" />
        )}
        <span className="truncate">{folder.name}</span>
      </button>

      {expanded && children.length > 0 && (
        <ul className="pl-4">
          {children.map((child) => (
            <FolderNode
              key={child.id}
              folder={child}
              allFolders={allFolders}
              currentFolderId={currentFolderId}
              onSelectFolder={onSelectFolder}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

interface FolderTreeProps {
  folders: StorageFolder[];
  currentFolderId: string | null;
  onSelectFolder: (id: string | null) => void;
  onFolderCreated: (folder: StorageFolder) => void;
}

export function FolderTree({
  folders,
  currentFolderId,
  onSelectFolder,
  onFolderCreated,
}: FolderTreeProps) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (creating && inputRef.current) {
      inputRef.current.focus();
    }
  }, [creating]);

  const rootFolders = folders.filter((f) => f.parent_folder_id === null);

  async function confirmCreate() {
    const name = newName.trim();
    if (!name) {
      setCreating(false);
      setNewName("");
      return;
    }
    try {
      const res = await fetch("/api/storage/folders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name,
          parent_folder_id: currentFolderId ?? null,
        }),
      });
      if (res.ok) {
        const folder = (await res.json()) as StorageFolder;
        onFolderCreated(folder);
      }
    } finally {
      setCreating(false);
      setNewName("");
    }
  }

  return (
    <div className="flex flex-col gap-1">
      {/* New Folder button */}
      <div className="px-2 pb-1">
        {creating ? (
          <input
            ref={inputRef}
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onBlur={confirmCreate}
            onKeyDown={(e) => {
              if (e.key === "Enter") void confirmCreate();
              if (e.key === "Escape") {
                setCreating(false);
                setNewName("");
              }
            }}
            placeholder="Folder name..."
            className="w-full text-sm px-2 py-1 border border-blue-400 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        ) : (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-blue-600 transition-colors"
          >
            <Plus size={13} />
            New folder
          </button>
        )}
      </div>

      <ul className="space-y-0.5">
        {/* Root "My Files" item */}
        <li>
          <button
            type="button"
            onClick={() => onSelectFolder(null)}
            className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-sm rounded-md transition-colors ${
              currentFolderId === null
                ? "bg-primary/10 text-blue-700 font-medium"
                : "text-gray-700 hover:bg-gray-100"
            }`}
          >
            <span className="w-3.5 shrink-0" />
            {currentFolderId === null ? (
              <FolderOpen size={15} className="shrink-0 text-blue-500" />
            ) : (
              <Folder size={15} className="shrink-0 text-yellow-500" />
            )}
            My Files
          </button>
        </li>

        {rootFolders.map((folder) => (
          <FolderNode
            key={folder.id}
            folder={folder}
            allFolders={folders}
            currentFolderId={currentFolderId}
            onSelectFolder={onSelectFolder}
          />
        ))}
      </ul>

      {/* Shared with me */}
      <div className="mt-2 border-t border-gray-200 pt-2 px-2">
        <button
          type="button"
          onClick={() => onSelectFolder("shared-with-me")}
          className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-sm rounded-md transition-colors ${
            currentFolderId === "shared-with-me"
              ? "bg-primary/10 text-blue-700 font-medium"
              : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          }`}
        >
          <span className="w-3.5 shrink-0" />
          <Folder size={15} className="shrink-0 text-gray-400" />
          Shared with me
        </button>
      </div>
    </div>
  );
}
