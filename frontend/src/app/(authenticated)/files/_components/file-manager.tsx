"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import type {
  StorageFile,
  StorageFolder,
  UploadProgress,
  DedupResponse,
} from "../types";
import { FolderTree } from "./folder-tree";
import { Breadcrumb } from "./breadcrumb";
import { Toolbar } from "./toolbar";
import { FileGrid } from "./file-grid";
import { FileList } from "./file-list";
import { UploadTray } from "./upload-tray";
import { ShareDialog } from "./share-dialog";

export function FileManager() {
  const [folders, setFolders] = useState<StorageFolder[]>([]);
  const [files, setFiles] = useState<StorageFile[]>([]);
  const [sharedFiles, setSharedFiles] = useState<StorageFile[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [uploads, setUploads] = useState<UploadProgress[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [shareDialogFile, setShareDialogFile] = useState<StorageFile | null>(
    null
  );
  const [breadcrumbPath, setBreadcrumbPath] = useState<StorageFolder[]>([]);
  const [loading, setLoading] = useState(true);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Fetch folders and files on mount ─────────────────────────────────
  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [foldersRes, filesRes] = await Promise.all([
        fetch("/api/storage/folders", { credentials: "include" }),
        fetch("/api/storage/files", { credentials: "include" }),
      ]);
      if (foldersRes.ok) {
        setFolders((await foldersRes.json()) as StorageFolder[]);
      }
      if (filesRes.ok) {
        const data = (await filesRes.json()) as {
          files: StorageFile[];
          total: number;
        };
        setFiles(data.files ?? (data as unknown as { items: StorageFile[] }).items ?? []);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  // ── Fetch shared-with-me when that virtual folder is selected ─────────
  useEffect(() => {
    if (currentFolderId !== "shared-with-me") return;
    void fetch("/api/storage/shared-with-me", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : { files: [], folders: [] }))
      .then((data: { files: StorageFile[]; folders: StorageFolder[] }) => {
        setSharedFiles(data.files ?? []);
      });
  }, [currentFolderId]);

  // ── Breadcrumb path update on folder navigation ───────────────────────
  function buildBreadcrumb(
    folderId: string | null,
    allFolders: StorageFolder[]
  ): StorageFolder[] {
    if (!folderId || folderId === "shared-with-me") return [];
    const path: StorageFolder[] = [];
    let current: StorageFolder | undefined = allFolders.find(
      (f) => f.id === folderId
    );
    while (current) {
      path.unshift(current);
      if (!current.parent_folder_id) break;
      current = allFolders.find((f) => f.id === current!.parent_folder_id);
    }
    return path;
  }

  function handleSelectFolder(id: string | null) {
    setCurrentFolderId(id);
    setSearchQuery("");
    setBreadcrumbPath(buildBreadcrumb(id, folders));
  }

  function handleBreadcrumbNavigate(folderId: string | null) {
    setCurrentFolderId(folderId);
    setBreadcrumbPath(buildBreadcrumb(folderId, folders));
  }

  // ── Displayed files (filtered by folder + search) ─────────────────────
  const displayedFiles = (() => {
    let source: StorageFile[];
    if (currentFolderId === "shared-with-me") {
      source = sharedFiles;
    } else if (currentFolderId === null) {
      // "My Files" root shows all owned files
      source = files;
    } else {
      source = files.filter((f) => f.folder_id === currentFolderId);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      source = source.filter((f) => f.name.toLowerCase().includes(q));
    }
    return source;
  })();

  // ── Upload handling ───────────────────────────────────────────────────
  const handleUpload = useCallback(
    async (acceptedFiles: File[]) => {
      const newUploads: UploadProgress[] = acceptedFiles.map((file) => ({
        file,
        progress: 0,
        status: "uploading" as const,
      }));
      setUploads((prev) => [...prev, ...newUploads]);

      for (const file of acceptedFiles) {
        const formData = new FormData();
        formData.append("file", file);
        if (currentFolderId && currentFolderId !== "shared-with-me") {
          formData.append("folder_id", currentFolderId);
        }

        try {
          // Simulate progress with XHR (fetch doesn't expose upload progress)
          setUploads((prev) =>
            prev.map((u) =>
              u.file.name === file.name ? { ...u, progress: 30 } : u
            )
          );

          const res = await fetch("/api/storage/files/upload", {
            method: "POST",
            credentials: "include",
            body: formData,
          });

          setUploads((prev) =>
            prev.map((u) =>
              u.file.name === file.name ? { ...u, progress: 90 } : u
            )
          );

          if (!res.ok) {
            setUploads((prev) =>
              prev.map((u) =>
                u.file.name === file.name
                  ? { ...u, status: "error", progress: 0 }
                  : u
              )
            );
            continue;
          }

          const data = (await res.json()) as
            | StorageFile
            | DedupResponse;

          if ("action" in data && data.action === "duplicate_detected") {
            setUploads((prev) =>
              prev.map((u) =>
                u.file.name === file.name
                  ? {
                      ...u,
                      status: "duplicate",
                      dedupInfo: {
                        existing_file_id: data.existing_file_id,
                        existing_file_name: data.existing_file_name,
                      },
                    }
                  : u
              )
            );
          } else {
            setUploads((prev) =>
              prev.map((u) =>
                u.file.name === file.name
                  ? { ...u, status: "done", progress: 100 }
                  : u
              )
            );
            // Append new file to list
            setFiles((prev) => [...prev, data as StorageFile]);
          }
        } catch {
          setUploads((prev) =>
            prev.map((u) =>
              u.file.name === file.name
                ? { ...u, status: "error", progress: 0 }
                : u
            )
          );
        }
      }
    },
    [currentFolderId]
  );

  // ── Dedup choice handler ──────────────────────────────────────────────
  async function handleDedupChoice(
    fileName: string,
    choice: "keep_both" | "replace" | "skip"
  ) {
    if (choice === "skip") {
      setUploads((prev) => prev.filter((u) => u.file.name !== fileName));
      return;
    }
    const upload = uploads.find((u) => u.file.name === fileName);
    if (!upload) return;

    const formData = new FormData();
    formData.append("file", upload.file);
    formData.append("action", choice);
    if (currentFolderId && currentFolderId !== "shared-with-me") {
      formData.append("folder_id", currentFolderId);
    }

    setUploads((prev) =>
      prev.map((u) =>
        u.file.name === fileName
          ? { ...u, status: "uploading", progress: 50 }
          : u
      )
    );

    try {
      const res = await fetch("/api/storage/files/upload", {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      if (res.ok) {
        const data = (await res.json()) as StorageFile;
        setFiles((prev) => {
          if (choice === "replace") {
            return prev.map((f) =>
              f.name === fileName ? (data as StorageFile) : f
            );
          }
          return [...prev, data as StorageFile];
        });
        setUploads((prev) =>
          prev.map((u) =>
            u.file.name === fileName
              ? { ...u, status: "done", progress: 100 }
              : u
          )
        );
      }
    } catch {
      setUploads((prev) =>
        prev.map((u) =>
          u.file.name === fileName
            ? { ...u, status: "error", progress: 0 }
            : u
        )
      );
    }
  }

  // ── Dropzone setup ────────────────────────────────────────────────────
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleUpload,
    noClick: true, // don't open on click — only on explicit upload button
    noKeyboard: true,
  });

  // ── File action handler ───────────────────────────────────────────────
  async function handleFileAction(action: string, file: StorageFile) {
    if (action === "download") {
      if (file.download_url) {
        window.open(file.download_url, "_blank");
      } else {
        // Fetch fresh download URL
        const res = await fetch(`/api/storage/files/${file.id}`, {
          credentials: "include",
        });
        if (res.ok) {
          const data = (await res.json()) as StorageFile;
          if (data.download_url) window.open(data.download_url, "_blank");
        }
      }
    } else if (action === "share") {
      setShareDialogFile(file);
    } else if (action === "add-to-memory") {
      const res = await fetch(`/api/storage/files/${file.id}/add-to-memory`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        toast.success("File queued for memory indexing");
        setFiles((prev) =>
          prev.map((f) => (f.id === file.id ? { ...f, in_memory: true } : f))
        );
      } else {
        toast.error("Failed to queue file for memory indexing");
      }
    } else if (action === "delete") {
      if (!confirm(`Delete "${file.name}"?`)) return;
      const res = await fetch(`/api/storage/files/${file.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        setFiles((prev) => prev.filter((f) => f.id !== file.id));
        toast.success("File deleted");
      } else {
        toast.error("Failed to delete file");
      }
    }
  }

  return (
    <div className="flex h-full bg-white">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-gray-200 overflow-y-auto bg-gray-50 py-3">
        <FolderTree
          folders={folders}
          currentFolderId={currentFolderId}
          onSelectFolder={handleSelectFolder}
          onFolderCreated={(folder) => {
            setFolders((prev) => [...prev, folder]);
          }}
        />
      </aside>

      {/* Main area with dropzone */}
      <div
        {...getRootProps()}
        className={`flex-1 flex flex-col min-w-0 relative ${
          isDragActive ? "bg-blue-50 ring-2 ring-inset ring-blue-400" : ""
        }`}
      >
        {/* Hidden dropzone input */}
        <input {...getInputProps()} />

        {isDragActive && (
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
            <p className="text-blue-600 text-lg font-semibold bg-white/80 px-6 py-3 rounded-xl shadow">
              Drop files to upload
            </p>
          </div>
        )}

        {/* Hidden file input for toolbar Upload button */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) {
              void handleUpload(Array.from(e.target.files));
              e.target.value = "";
            }
          }}
        />

        {/* Breadcrumb */}
        <Breadcrumb
          path={breadcrumbPath}
          onNavigate={handleBreadcrumbNavigate}
        />

        {/* Toolbar */}
        <Toolbar
          viewMode={viewMode}
          onViewChange={setViewMode}
          onUploadClick={() => fileInputRef.current?.click()}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        {/* File display */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
              Loading files...
            </div>
          ) : viewMode === "grid" ? (
            <FileGrid files={displayedFiles} onAction={handleFileAction} />
          ) : (
            <FileList files={displayedFiles} onAction={handleFileAction} />
          )}
        </div>
      </div>

      {/* Upload tray */}
      <UploadTray
        uploads={uploads}
        onDismiss={(name) =>
          setUploads((prev) => prev.filter((u) => u.file.name !== name))
        }
        onDedupChoice={handleDedupChoice}
        onDismissAll={() => setUploads([])}
      />

      {/* Share dialog */}
      <ShareDialog
        file={shareDialogFile}
        onClose={() => setShareDialogFile(null)}
      />
    </div>
  );
}
