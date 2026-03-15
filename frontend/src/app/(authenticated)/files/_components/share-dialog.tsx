"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { X, Search, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import type { StorageFile, StorageShare, ShareUser } from "../types";

interface ShareDialogProps {
  file: StorageFile | null;
  onClose: () => void;
}

type Permission = "READ" | "WRITE" | "ADMIN";

interface PendingShare {
  user: ShareUser;
  permission: Permission;
}

const PERMISSION_LABELS: Record<Permission, string> = {
  READ: "Can view",
  WRITE: "Can edit",
  ADMIN: "Admin",
};

export function ShareDialog({ file, onClose }: ShareDialogProps) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ShareUser[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [pending, setPending] = useState<PendingShare[]>([]);
  const [existingShares, setExistingShares] = useState<StorageShare[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch existing shares when file changes
  useEffect(() => {
    if (!file) return;
    void fetch(`/api/storage/shares/${file.id}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((data: StorageShare[]) => setExistingShares(data));
  }, [file]);

  // Typeahead search with 300ms debounce
  const doSearch = useCallback((q: string) => {
    if (!q.trim()) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    void fetch(
      `/api/storage/users/search?q=${encodeURIComponent(q)}`,
      { credentials: "include" }
    )
      .then((r) => (r.ok ? r.json() : []))
      .then((data: ShareUser[]) => {
        setSuggestions(data);
        setShowSuggestions(true);
      });
  }, []);

  function handleQueryChange(value: string) {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(value), 300);
  }

  function selectUser(user: ShareUser) {
    // Avoid duplicates
    if (pending.some((p) => p.user.id === user.id)) {
      setQuery("");
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    setPending((prev) => [...prev, { user, permission: "READ" }]);
    setQuery("");
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function updatePermission(userId: string, permission: Permission) {
    setPending((prev) =>
      prev.map((p) => (p.user.id === userId ? { ...p, permission } : p))
    );
  }

  function removePending(userId: string) {
    setPending((prev) => prev.filter((p) => p.user.id !== userId));
  }

  async function handleShare() {
    if (!file || pending.length === 0) return;
    setSubmitting(true);
    try {
      await Promise.all(
        pending.map((p) =>
          fetch("/api/storage/shares", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
              resource_type: "file",
              resource_id: file.id,
              shared_with_user_id: p.user.id,
              permission: p.permission,
            }),
          })
        )
      );
      pending.forEach((p) =>
        toast.success(`File shared with ${p.user.email}`)
      );
      onClose();
    } finally {
      setSubmitting(false);
    }
  }

  async function revokeShare(shareId: string) {
    await fetch(`/api/storage/shares/${shareId}`, {
      method: "DELETE",
      credentials: "include",
    });
    setExistingShares((prev) => prev.filter((s) => s.id !== shareId));
    toast.success("Share revoked");
  }

  if (!file) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">
            Share &ldquo;{file.name}&rdquo;
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-700 transition-colors rounded"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Typeahead search */}
          <div className="relative">
            <div className="flex items-center gap-2 border border-gray-300 rounded-md px-3 py-2 focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent">
              <Search size={15} className="text-gray-400 shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => handleQueryChange(e.target.value)}
                placeholder="Search by email..."
                className="flex-1 text-sm outline-none"
              />
            </div>
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-md shadow-lg z-10 max-h-40 overflow-y-auto">
                {suggestions.map((user) => (
                  <button
                    key={user.id}
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition-colors"
                    onMouseDown={() => selectUser(user)}
                  >
                    <span className="font-medium">{user.display_name}</span>
                    <span className="text-gray-500 ml-1">{user.email}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Pending shares to add */}
          {pending.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                Add
              </p>
              {pending.map((p) => (
                <div
                  key={p.user.id}
                  className="flex items-center gap-2 bg-blue-50 rounded-md px-3 py-2"
                >
                  <span className="flex-1 text-sm text-gray-800 truncate">
                    {p.user.email}
                  </span>
                  <PermissionSelect
                    value={p.permission}
                    onChange={(perm) => updatePermission(p.user.id, perm)}
                  />
                  <button
                    type="button"
                    onClick={() => removePending(p.user.id)}
                    className="p-0.5 text-gray-400 hover:text-gray-700 rounded"
                  >
                    <X size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Existing shares */}
          {existingShares.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                Existing access
              </p>
              {existingShares.map((share) => (
                <div
                  key={share.id}
                  className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-md"
                >
                  <span className="flex-1 text-sm text-gray-700 truncate">
                    {share.shared_with_user_id}
                  </span>
                  <span className="text-xs text-gray-500">
                    {share.permission}
                  </span>
                  <button
                    type="button"
                    onClick={() => void revokeShare(share.id)}
                    className="text-xs text-red-500 hover:text-red-700 transition-colors ml-1"
                  >
                    Revoke
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-200 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={pending.length === 0 || submitting}
            onClick={() => void handleShare()}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Sharing..." : "Share"}
          </button>
        </div>
      </div>
    </div>
  );
}

interface PermissionSelectProps {
  value: Permission;
  onChange: (p: Permission) => void;
}

function PermissionSelect({ value, onChange }: PermissionSelectProps) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as Permission)}
        className="appearance-none text-xs pl-2 pr-6 py-1 border border-gray-300 rounded bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        {(Object.keys(PERMISSION_LABELS) as Permission[]).map((p) => (
          <option key={p} value={p}>
            {PERMISSION_LABELS[p]}
          </option>
        ))}
      </select>
      <ChevronDown
        size={10}
        className="absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none text-gray-500"
      />
    </div>
  );
}
