"use client";

import { X, CheckCircle, AlertCircle, Loader2, ChevronDown } from "lucide-react";
import { useState } from "react";
import type { UploadProgress } from "../types";

interface UploadTrayProps {
  uploads: UploadProgress[];
  onDismiss: (uploadId: string) => void;
  onDedupChoice: (
    uploadId: string,
    choice: "keep_both" | "replace" | "skip"
  ) => void;
  onDismissAll: () => void;
}

export function UploadTray({
  uploads,
  onDismiss,
  onDedupChoice,
  onDismissAll,
}: UploadTrayProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (uploads.length === 0) return null;

  const allDone = uploads.every(
    (u) => u.status === "done" || u.status === "error"
  );
  // If any are still "duplicate" awaiting choice, not all done
  const hasPending = uploads.some(
    (u) => u.status === "uploading" || u.status === "duplicate"
  );

  return (
    <div className="fixed bottom-4 right-4 w-80 z-50 bg-white border border-gray-200 rounded-lg shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-200">
        <span className="text-sm font-semibold text-gray-800">
          Uploads ({uploads.length})
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setCollapsed((prev) => !prev)}
            className="p-1 text-gray-400 hover:text-gray-700 transition-colors rounded"
            title={collapsed ? "Expand" : "Collapse"}
          >
            <ChevronDown
              size={14}
              className={`transition-transform ${collapsed ? "-rotate-90" : ""}`}
            />
          </button>
          {(allDone || !hasPending) && (
            <button
              type="button"
              onClick={onDismissAll}
              className="p-1 text-gray-400 hover:text-gray-700 transition-colors rounded"
              title="Dismiss all"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* File rows */}
      {!collapsed && (
        <div className="max-h-72 overflow-y-auto divide-y divide-gray-100">
          {uploads.map((upload) => (
            <div key={upload.id} className="px-3 py-2">
              <div className="flex items-center gap-2">
                {/* Status icon */}
                <span className="shrink-0">
                  {upload.status === "uploading" && (
                    <Loader2 size={15} className="animate-spin text-blue-500" />
                  )}
                  {upload.status === "done" && (
                    <CheckCircle size={15} className="text-green-500" />
                  )}
                  {upload.status === "error" && (
                    <AlertCircle size={15} className="text-red-500" />
                  )}
                  {upload.status === "duplicate" && (
                    <AlertCircle size={15} className="text-amber-500" />
                  )}
                </span>

                <span className="text-xs text-gray-700 truncate flex-1">
                  {upload.file.name}
                </span>

                {(upload.status === "done" || upload.status === "error") && (
                  <button
                    type="button"
                    onClick={() => onDismiss(upload.id)}
                    className="shrink-0 p-0.5 text-gray-300 hover:text-gray-600 transition-colors"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>

              {/* Progress bar */}
              {upload.status === "uploading" && (
                <div className="mt-1.5 h-1 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 transition-all duration-300"
                    style={{ width: `${upload.progress}%` }}
                  />
                </div>
              )}

              {/* Duplicate choice */}
              {upload.status === "duplicate" && upload.dedupInfo && (
                <div className="mt-1.5">
                  <p className="text-xs text-amber-700 mb-1.5">
                    Duplicate of &ldquo;{upload.dedupInfo.existing_file_name}&rdquo;
                  </p>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() =>
                        onDedupChoice(upload.id, "keep_both")
                      }
                      className="flex-1 text-xs py-1 px-1.5 bg-gray-100 hover:bg-gray-200 rounded transition-colors"
                    >
                      Keep both
                    </button>
                    <button
                      type="button"
                      onClick={() => onDedupChoice(upload.id, "replace")}
                      className="flex-1 text-xs py-1 px-1.5 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded transition-colors"
                    >
                      Replace
                    </button>
                    <button
                      type="button"
                      onClick={() => onDedupChoice(upload.id, "skip")}
                      className="flex-1 text-xs py-1 px-1.5 bg-gray-100 hover:bg-gray-200 rounded transition-colors"
                    >
                      Skip
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
