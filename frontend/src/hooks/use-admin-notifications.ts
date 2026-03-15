"use client";
/**
 * Hook for admin notification CRUD.
 *
 * Polls GET /api/admin/notifications/count every 30s for badge count.
 * Fetches full list on demand (when dropdown opens).
 */
import { useState, useEffect, useCallback, useRef } from "react";
import {
  AdminNotificationSchema,
  NotificationCountSchema,
  type AdminNotification,
} from "@/lib/api-types";
import { z } from "zod";

interface UseAdminNotificationsReturn {
  notifications: AdminNotification[];
  unreadCount: number;
  totalCount: number;
  loading: boolean;
  fetchNotifications: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
  refresh: () => Promise<void>;
}

export function useAdminNotifications(): UseAdminNotificationsReturn {
  const [notifications, setNotifications] = useState<AdminNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchCount = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/notifications/count");
      if (!res.ok) return;
      const data: unknown = await res.json();
      const parsed = NotificationCountSchema.parse(data);
      setUnreadCount(parsed.unread);
      setTotalCount(parsed.total);
    } catch {
      // Non-critical — swallow
    }
  }, []);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/notifications?limit=10");
      if (!res.ok) return;
      const data: unknown = await res.json();
      const parsed = z.array(AdminNotificationSchema).parse(data);
      setNotifications(parsed);
    } catch {
      // Non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll count on mount + every 30s
  useEffect(() => {
    void fetchCount();
    intervalRef.current = setInterval(() => void fetchCount(), 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchCount]);

  const markRead = useCallback(
    async (id: string) => {
      try {
        await fetch(`/api/admin/notifications/${id}/read`, { method: "POST" });
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch {
        // Non-critical
      }
    },
    []
  );

  const markAllRead = useCallback(async () => {
    try {
      await fetch("/api/admin/notifications/read-all", { method: "POST" });
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Non-critical
    }
  }, []);

  const refresh = useCallback(async () => {
    await Promise.all([fetchCount(), fetchNotifications()]);
  }, [fetchCount, fetchNotifications]);

  return {
    notifications,
    unreadCount,
    totalCount,
    loading,
    fetchNotifications,
    markRead,
    markAllRead,
    refresh,
  };
}
