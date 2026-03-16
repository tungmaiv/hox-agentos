/**
 * Storage Service — TypeScript type contracts.
 * Mirrors the backend Pydantic schemas from plan 28-02.
 */

export interface StorageFile {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number;
  content_hash: string;
  folder_id: string | null;
  owner_user_id: string;
  owner_username?: string | null;
  in_memory: boolean;
  created_at: string;
  updated_at: string;
  download_url?: string;
}

export interface StorageFolder {
  id: string;
  name: string;
  parent_folder_id: string | null;
  owner_user_id: string;
  created_at: string;
}

export interface StorageShare {
  id: string;
  file_id: string | null;
  folder_id: string | null;
  shared_with_user_id: string;
  shared_by_user_id: string;
  permission: "READ" | "WRITE" | "ADMIN";
  created_at: string;
}

export interface UploadProgress {
  id: string; // stable identifier generated at batch creation to avoid same-name collisions
  file: File;
  progress: number; // 0-100
  status: "uploading" | "done" | "duplicate" | "error";
  dedupInfo?: { existing_file_id: string; existing_file_name: string };
}

export interface DedupResponse {
  action: "duplicate_detected";
  existing_file_id: string;
  existing_file_name: string;
  content_hash: string;
}

export interface ShareUser {
  id: string;
  email: string;
  display_name: string;
}

/**
 * MIME types that are extractable for memory indexing.
 * Mirrors backend storage_service.py EXTRACTABLE_MIME_TYPES.
 */
export const EXTRACTABLE_MIME_TYPES: Set<string> = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/markdown",
]);

/**
 * Converts bytes to a human-readable string (KB / MB / GB).
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/**
 * Returns the relative time string for a date string (e.g. "2 days ago").
 */
export function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  const diffMo = Math.floor(diffDay / 30);
  if (diffMo < 12) return `${diffMo}mo ago`;
  return `${Math.floor(diffMo / 12)}y ago`;
}
