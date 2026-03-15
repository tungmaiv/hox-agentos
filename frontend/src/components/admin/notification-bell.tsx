"use client";
/**
 * Admin notification bell icon with unread badge and dropdown.
 *
 * Shows recent admin notifications (SSO health alerts, etc.).
 * Badge displays unread count; clicking opens a dropdown with the latest 10.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { Bell } from "lucide-react";
import { useAdminNotifications } from "@/hooks/use-admin-notifications";

// ---------------------------------------------------------------------------
// Severity styling
// ---------------------------------------------------------------------------

const SEVERITY_COLORS: Record<string, string> = {
  critical: "text-red-600",
  warning: "text-yellow-600",
  info: "text-blue-600",
};

function relativeTime(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function NotificationBell() {
  const {
    notifications,
    unreadCount,
    loading,
    fetchNotifications,
    markRead,
    markAllRead,
  } = useAdminNotifications();

  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
      setOpen(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open, handleClickOutside]);

  function handleToggle() {
    const willOpen = !open;
    setOpen(willOpen);
    if (willOpen) {
      void fetchNotifications();
    }
  }

  async function handleMarkRead(id: string) {
    await markRead(id);
  }

  async function handleMarkAllRead() {
    await markAllRead();
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={handleToggle}
        className="relative p-1 rounded hover:bg-gray-100 transition-colors"
        title="Admin notifications"
      >
        <Bell className="h-5 w-5 text-gray-600" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center leading-none">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-80 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-900">Notifications</span>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => void handleMarkAllRead()}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto">
            {loading && notifications.length === 0 ? (
              <p className="px-4 py-3 text-xs text-gray-400">Loading...</p>
            ) : notifications.length === 0 ? (
              <p className="px-4 py-3 text-xs text-gray-400">No notifications</p>
            ) : (
              notifications.map((n) => {
                const severityColor = SEVERITY_COLORS[n.severity] ?? "text-gray-600";
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => void handleMarkRead(n.id)}
                    className={`w-full text-left px-4 py-2.5 hover:bg-gray-50 border-b border-gray-50 last:border-b-0 ${
                      n.is_read ? "opacity-60" : ""
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <span className={`text-xs font-medium mt-0.5 ${severityColor}`}>
                        {n.severity === "critical" ? "!" : n.severity === "warning" ? "!" : "i"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className={`text-sm ${n.is_read ? "text-gray-600" : "text-gray-900 font-medium"}`}>
                            {n.title}
                          </span>
                          <span className="text-xs text-gray-400 shrink-0">
                            {relativeTime(n.created_at)}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{n.message}</p>
                      </div>
                      {!n.is_read && (
                        <span className="mt-1.5 h-2 w-2 rounded-full bg-blue-500 shrink-0" />
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
