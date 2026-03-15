"use client";
/**
 * UserNotificationBell — per-user share notification bell for the nav rail.
 *
 * Shows a Bell icon (lucide-react) with a red badge when unread share notifications exist.
 * Polls GET /api/storage/notifications every 30s.
 * On click: opens a dropdown showing last 5 unread notifications.
 * Clicking a notification marks it as read (POST /api/storage/notifications/{id}/read).
 * "Mark all as read" button at bottom clears all notifications.
 *
 * Separation: This is NOT the admin notification bell (/api/admin/notifications).
 * Only shows user_notifications for file shares, etc.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { Bell } from "lucide-react";
import { useSession } from "next-auth/react";

interface UserNotification {
  id: string;
  title: string;
  message: string | null;
  notification_type: string;
  is_read: boolean;
  created_at: string;
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export default function UserNotificationBell() {
  const { data: session } = useSession();
  const [notifications, setNotifications] = useState<UserNotification[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [markingAll, setMarkingAll] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const getToken = useCallback((): string | undefined => {
    return (session as unknown as Record<string, unknown>)?.accessToken as string | undefined;
  }, [session]);

  const fetchNotifications = useCallback(async () => {
    try {
      const token = getToken();
      if (!token) return;

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/storage/notifications`,
        {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        }
      );
      if (!res.ok) return;
      const data = (await res.json()) as UserNotification[];
      setNotifications(data);
    } catch {
      // Bell is non-critical — swallow errors
    }
  }, [getToken]);

  // Initial fetch + polling every 30s
  useEffect(() => {
    void fetchNotifications();
    const interval = setInterval(() => void fetchNotifications(), 30000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [dropdownOpen]);

  const handleMarkRead = async (notificationId: string) => {
    try {
      const token = getToken();
      if (!token) return;

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/storage/notifications/${notificationId}/read`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (res.ok) {
        // Optimistically remove from unread list
        setNotifications((prev) => prev.filter((n) => n.id !== notificationId));
      }
    } catch {
      // Non-critical — swallow
    }
  };

  const handleMarkAllRead = async () => {
    setMarkingAll(true);
    try {
      const token = getToken();
      if (!token) return;

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/storage/notifications/read-all`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (res.ok) {
        setNotifications([]);
        setDropdownOpen(false);
      }
    } catch {
      // Non-critical — swallow
    } finally {
      setMarkingAll(false);
    }
  };

  const unreadCount = notifications.length;
  const displayNotifications = notifications.slice(0, 5);

  return (
    <div ref={dropdownRef} className="relative">
      <button
        type="button"
        title="Share notifications"
        onClick={() => setDropdownOpen((prev) => !prev)}
        className="relative flex items-center justify-center w-full h-14 text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-colors"
        aria-haspopup="true"
        aria-expanded={dropdownOpen}
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="absolute top-2 right-2 bg-red-500 text-white text-xs font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 leading-none">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {dropdownOpen && (
        <div className="absolute left-full bottom-0 ml-2 w-72 bg-white border border-gray-200 rounded-lg shadow-xl z-50">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-700">Share Notifications</p>
            {unreadCount === 0 && (
              <p className="text-xs text-gray-400 mt-0.5">No new notifications</p>
            )}
          </div>

          {displayNotifications.length > 0 && (
            <ul className="py-1 max-h-64 overflow-y-auto">
              {displayNotifications.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => void handleMarkRead(notification.id)}
                    className="w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors"
                  >
                    <p className="text-sm font-medium text-gray-800 truncate">
                      {notification.title}
                    </p>
                    {notification.message && (
                      <p className="text-xs text-gray-500 mt-0.5 truncate">
                        {notification.message}
                      </p>
                    )}
                    <p className="text-xs text-gray-400 mt-1">
                      {formatRelativeTime(notification.created_at)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {unreadCount > 0 && (
            <div className="px-4 py-3 border-t border-gray-100">
              <button
                type="button"
                onClick={() => void handleMarkAllRead()}
                disabled={markingAll}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {markingAll ? "Clearing..." : "Mark all as read"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
