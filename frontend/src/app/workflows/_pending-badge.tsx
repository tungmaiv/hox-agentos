"use client";

import { usePendingHitl } from "@/hooks/use-pending-hitl";

export function PendingBadge() {
  const count = usePendingHitl();
  if (count === 0) return null;
  return (
    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
      {count} pending
    </span>
  );
}
