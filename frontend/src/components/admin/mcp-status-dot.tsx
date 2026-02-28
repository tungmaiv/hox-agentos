"use client";
/**
 * McpStatusDot — colored connectivity indicator for MCP servers.
 *
 * Color logic based on last_seen_at timestamp:
 * - Green: seen within the last 5 minutes
 * - Yellow: seen within the last 30 minutes
 * - Red: seen more than 30 minutes ago or never seen (null)
 *
 * Includes a tooltip showing the exact last-seen time.
 */

interface McpStatusDotProps {
  lastSeenAt: string | null;
}

function getStatusColor(lastSeenAt: string | null): {
  color: string;
  bgClass: string;
  label: string;
} {
  if (!lastSeenAt) {
    return {
      color: "red",
      bgClass: "bg-red-500",
      label: "Never connected",
    };
  }

  const lastSeen = new Date(lastSeenAt);
  const now = new Date();
  const diffMs = now.getTime() - lastSeen.getTime();
  const diffMinutes = diffMs / (1000 * 60);

  if (diffMinutes < 5) {
    return {
      color: "green",
      bgClass: "bg-green-500",
      label: "Connected (< 5 min ago)",
    };
  }

  if (diffMinutes < 30) {
    return {
      color: "yellow",
      bgClass: "bg-yellow-500",
      label: "Stale (< 30 min ago)",
    };
  }

  return {
    color: "red",
    bgClass: "bg-red-500",
    label: "Disconnected (> 30 min ago)",
  };
}

function formatLastSeen(lastSeenAt: string | null): string {
  if (!lastSeenAt) return "Never";
  const date = new Date(lastSeenAt);
  return date.toLocaleString();
}

export function McpStatusDot({ lastSeenAt }: McpStatusDotProps) {
  const { bgClass, label } = getStatusColor(lastSeenAt);

  return (
    <span className="relative group inline-flex items-center">
      <span
        className={`inline-block w-2.5 h-2.5 rounded-full ${bgClass}`}
        aria-label={label}
      />
      {/* Tooltip */}
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20">
        {label}
        <br />
        Last seen: {formatLastSeen(lastSeenAt)}
      </span>
    </span>
  );
}
