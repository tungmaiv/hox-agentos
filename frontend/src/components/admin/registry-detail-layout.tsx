"use client";
/**
 * RegistryDetailLayout — reusable detail page shell for registry entries.
 *
 * Provides breadcrumb, header (name, description, status badge, timestamps),
 * tab bar, children slot, and StickySaveBar integration. Adds beforeunload
 * listener when hasChanges is true.
 */
import { useEffect } from "react";
import Link from "next/link";
import type { RegistryEntry } from "@/lib/admin-types";
import { StickySaveBar } from "./sticky-save-bar";

interface RegistryDetailLayoutProps {
  entry: RegistryEntry;
  backHref: string;
  backLabel: string;
  tabs: { id: string; label: string }[];
  activeTab: string;
  onTabChange: (tab: string) => void;
  children: React.ReactNode;
  hasChanges?: boolean;
  saving?: boolean;
  onSave?: () => void;
  onDiscard?: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  disabled: "bg-gray-100 text-gray-500",
  deprecated: "bg-yellow-100 text-yellow-700",
  pending_review: "bg-orange-100 text-orange-700",
  draft: "bg-blue-100 text-blue-700",
  archived: "bg-gray-100 text-gray-500",
};

export function RegistryDetailLayout({
  entry,
  backHref,
  backLabel,
  tabs,
  activeTab,
  onTabChange,
  children,
  hasChanges = false,
  saving = false,
  onSave,
  onDiscard,
}: RegistryDetailLayoutProps) {
  // Warn user about leaving with unsaved changes
  useEffect(() => {
    if (!hasChanges) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasChanges]);

  const statusColor =
    STATUS_COLORS[entry.status] ?? "bg-gray-100 text-gray-600";

  return (
    <div className={hasChanges ? "pb-16" : ""}>
      {/* Breadcrumb */}
      <div className="mb-4">
        <Link
          href={backHref}
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; {backLabel}
        </Link>
        <span className="text-gray-400 text-sm mx-2">/</span>
        <span className="text-sm text-gray-700 font-medium">{entry.name}</span>
      </div>

      {/* Header */}
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-gray-900">
          {entry.displayName ?? entry.name}
        </h2>
        {entry.description && (
          <p className="text-sm text-gray-500 mt-1">{entry.description}</p>
        )}
        <div className="flex items-center gap-3 mt-2">
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}
          >
            {entry.status}
          </span>
          <span className="text-xs text-gray-400">
            Created {new Date(entry.createdAt).toLocaleDateString()}
          </span>
          <span className="text-xs text-gray-400">
            Updated {new Date(entry.updatedAt).toLocaleDateString()}
          </span>
        </div>
      </div>

      {/* Tab bar */}
      <div className="border-b border-gray-200 mb-4">
        <div className="flex gap-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "text-blue-600 border-blue-600"
                  : "text-gray-500 border-transparent hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Children slot */}
      {children}

      {/* Sticky save bar */}
      {onSave && onDiscard && (
        <StickySaveBar
          hasChanges={hasChanges}
          saving={saving}
          onSave={onSave}
          onDiscard={onDiscard}
        />
      )}
    </div>
  );
}
