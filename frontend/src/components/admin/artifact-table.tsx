"use client";
/**
 * ArtifactTable — generic table view for admin artifact management.
 *
 * Displays artifacts in a sortable table with status badges, action buttons
 * (edit, enable/disable, activate version), and filter controls.
 *
 * Generic over T which must extend ArtifactBase.
 */
import { useState } from "react";
import type { ArtifactBase, ArtifactStatus } from "@/lib/admin-types";

type SortField = "name" | "version" | "status" | "lastSeenAt";
type SortDir = "asc" | "desc";

interface Column<T> {
  key: string;
  label: string;
  render: (item: T) => React.ReactNode;
  sortable?: boolean;
}

interface ArtifactTableProps<T extends ArtifactBase> {
  items: T[];
  columns?: Column<T>[];
  onEdit?: (item: T) => void;
  onPatchStatus?: (
    id: string,
    status: "active" | "disabled" | "deprecated"
  ) => void;
  onActivateVersion?: (id: string) => void;
}

function StatusBadge({ status }: { status: ArtifactStatus }) {
  const colors: Record<ArtifactStatus, string> = {
    active: "bg-green-100 text-green-800",
    disabled: "bg-gray-100 text-gray-600",
    deprecated: "bg-yellow-100 text-yellow-800",
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

export function ArtifactTable<T extends ArtifactBase>({
  items,
  columns,
  onEdit,
  onPatchStatus,
  onActivateVersion,
}: ArtifactTableProps<T>) {
  const [sortField, setSortField] = useState<SortField>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const filtered = items.filter(
    (item) => statusFilter === "all" || item.status === statusFilter
  );

  const sorted = [...filtered].sort((a, b) => {
    const dir = sortDir === "asc" ? 1 : -1;
    const aVal = a[sortField] ?? "";
    const bVal = b[sortField] ?? "";
    if (aVal < bVal) return -1 * dir;
    if (aVal > bVal) return 1 * dir;
    return 0;
  });

  const SortHeader = ({
    field,
    children,
  }: {
    field: SortField;
    children: React.ReactNode;
  }) => (
    <th
      className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700 select-none"
      onClick={() => toggleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {sortField === field && (
          <span className="text-blue-500">{sortDir === "asc" ? "^" : "v"}</span>
        )}
      </span>
    </th>
  );

  return (
    <div>
      {/* Filter bar */}
      <div className="mb-3 flex items-center gap-3">
        <select
          className="text-xs border border-gray-300 rounded-md px-2 py-1 bg-white text-gray-700"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
          <option value="deprecated">Deprecated</option>
        </select>
        <span className="text-xs text-gray-400">
          {sorted.length} item{sorted.length !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <SortHeader field="name">Name</SortHeader>
              <SortHeader field="version">Version</SortHeader>
              <SortHeader field="status">Status</SortHeader>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Active
              </th>
              <SortHeader field="lastSeenAt">Last Seen</SortHeader>
              {columns?.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {col.label}
                </th>
              ))}
              <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sorted.map((item) => (
              <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-2.5">
                  <div>
                    <span className="text-sm font-medium text-gray-900">
                      {item.displayName ?? item.name}
                    </span>
                    {item.displayName && (
                      <span className="text-xs text-gray-400 ml-1">
                        ({item.name})
                      </span>
                    )}
                  </div>
                  {item.description && (
                    <p className="text-xs text-gray-500 mt-0.5 truncate max-w-xs">
                      {item.description}
                    </p>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <span className="text-xs text-gray-600 font-mono">
                    {item.version}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <StatusBadge status={item.status} />
                </td>
                <td className="px-4 py-2.5">
                  {item.isActive ? (
                    <span className="text-green-600 text-sm" title="Active version">
                      &#10003;
                    </span>
                  ) : (
                    <span className="text-gray-300 text-sm">-</span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <RelativeTime dateStr={item.lastSeenAt} />
                </td>
                {columns?.map((col) => (
                  <td key={col.key} className="px-4 py-2.5">
                    {col.render(item)}
                  </td>
                ))}
                <td className="px-4 py-2.5 text-right">
                  <div className="inline-flex items-center gap-1">
                    {onEdit && (
                      <button
                        onClick={() => onEdit(item)}
                        className="text-xs px-2 py-1 text-blue-600 hover:bg-blue-50 rounded transition-colors"
                      >
                        Edit
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
                        className="text-xs px-2 py-1 text-purple-600 hover:bg-purple-50 rounded transition-colors"
                      >
                        Activate
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td
                  colSpan={6 + (columns?.length ?? 0)}
                  className="px-4 py-8 text-center text-sm text-gray-400"
                >
                  No artifacts found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
