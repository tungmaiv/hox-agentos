"use client";
/**
 * ArtifactCardGrid — generic card grid view for admin artifact management.
 *
 * Displays artifacts as responsive cards with status badges, action buttons
 * (edit, enable/disable, activate version, clone), and truncated descriptions.
 * Responsive: 3 cols on lg, 2 on md, 1 on sm.
 */
import { useRouter } from "next/navigation";
import type { ArtifactBase, ArtifactStatus } from "@/lib/admin-types";

function StatusBadge({ status }: { status: ArtifactStatus }) {
  const colors: Record<ArtifactStatus, string> = {
    active: "bg-green-100 text-green-800",
    disabled: "bg-gray-100 text-gray-600",
    deprecated: "bg-yellow-100 text-yellow-800",
    pending_review: "bg-orange-100 text-orange-800",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${colors[status] ?? "bg-gray-100 text-gray-600"}`}
    >
      {status}
    </span>
  );
}

function RelativeTime({ dateStr }: { dateStr: string | null }) {
  if (!dateStr) return <span className="text-gray-400 text-xs">Never</span>;
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);

  let text: string;
  if (diffMinutes < 1) text = "Just now";
  else if (diffMinutes < 60) text = `${diffMinutes}m ago`;
  else if (diffMinutes < 1440) text = `${Math.floor(diffMinutes / 60)}h ago`;
  else text = `${Math.floor(diffMinutes / 1440)}d ago`;

  return (
    <span className="text-xs text-gray-500" title={date.toLocaleString()}>
      {text}
    </span>
  );
}

interface ArtifactCardGridProps<T extends ArtifactBase> {
  items: T[];
  /** Render additional info on the card (e.g., handler_type for tools). */
  renderExtra?: (item: T) => React.ReactNode;
  /** Artifact type used for the clone URL query param (e.g., "agent", "tool"). */
  artifactType?: string;
  onEdit?: (item: T) => void;
  onPatchStatus?: (
    id: string,
    status: "active" | "disabled" | "deprecated"
  ) => void;
  onActivateVersion?: (id: string) => void;
}

export function ArtifactCardGrid<T extends ArtifactBase>({
  items,
  renderExtra,
  artifactType,
  onEdit,
  onPatchStatus,
  onActivateVersion,
}: ArtifactCardGridProps<T>) {
  const router = useRouter();
  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-400">
        No artifacts found
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((item) => (
        <div
          key={item.id}
          className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm transition-all"
        >
          {/* Header */}
          <div className="flex items-start justify-between mb-2">
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-medium text-gray-900 truncate">
                {item.displayName ?? item.name}
              </h3>
              {item.displayName && (
                <p className="text-xs text-gray-400 truncate">{item.name}</p>
              )}
            </div>
            <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
              <StatusBadge status={item.status} />
              {item.isActive && (
                <span
                  className="text-green-600 text-xs font-bold"
                  title="Active version"
                >
                  &#10003;
                </span>
              )}
            </div>
          </div>

          {/* Description */}
          {item.description && (
            <p className="text-xs text-gray-500 mb-3 line-clamp-2">
              {item.description}
            </p>
          )}

          {/* Meta row */}
          <div className="flex items-center gap-3 mb-3 text-xs text-gray-400">
            <span className="font-mono">v{item.version}</span>
            <span>
              Last seen: <RelativeTime dateStr={item.lastSeenAt} />
            </span>
          </div>

          {/* Extra content */}
          {renderExtra && (
            <div className="mb-3 text-xs text-gray-500">{renderExtra(item)}</div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-1 flex-wrap border-t border-gray-100 pt-2">
            {onEdit && (
              <button
                onClick={() => onEdit(item)}
                className="text-xs px-2 py-1 text-blue-600 hover:bg-blue-50 rounded transition-colors"
              >
                Edit
              </button>
            )}
            {artifactType && (
              <button
                onClick={() =>
                  router.push(
                    `/admin/create?clone_type=${artifactType}&clone_id=${item.id}`
                  )
                }
                className="text-xs px-2 py-1 text-gray-600 border border-gray-200 rounded hover:bg-gray-50 transition-colors"
              >
                Clone
              </button>
            )}
            {onPatchStatus && item.status === "active" && (
              <button
                onClick={() => onPatchStatus(item.id, "disabled")}
                className="text-xs px-2 py-1 text-orange-600 hover:bg-orange-50 rounded transition-colors"
              >
                Disable
              </button>
            )}
            {onPatchStatus && item.status !== "active" && (
              <button
                onClick={() => onPatchStatus(item.id, "active")}
                className="text-xs px-2 py-1 text-green-600 hover:bg-green-50 rounded transition-colors"
              >
                Enable
              </button>
            )}
            {onActivateVersion && !item.isActive && (
              <button
                onClick={() => onActivateVersion(item.id)}
                className="text-xs px-2 py-1 text-purple-600 hover:bg-purple-50 rounded transition-colors ml-auto"
              >
                Activate Version
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
