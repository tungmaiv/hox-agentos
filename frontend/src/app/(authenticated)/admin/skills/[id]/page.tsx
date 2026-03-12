"use client";
/**
 * Admin skill detail page — /admin/skills/[id].
 *
 * Shows skill details with tabbed view including a "Scan Results" tab
 * displaying security scan data from the registry entry config.
 */
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { mapSnakeToCamel } from "@/lib/admin-types";
import type { RegistryEntry } from "@/lib/admin-types";

// ---------------------------------------------------------------------------
// Security report type (matches backend SecurityScanResult schema)
// ---------------------------------------------------------------------------

interface SecurityReport {
  recommendation?: "approve" | "review" | "reject";
  scan_engine?: string;
  bandit_issues?: unknown[];
  pip_audit_issues?: unknown[];
  findings?: unknown[];
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

type Tab = "overview" | "config" | "scan-results";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "config", label: "Config" },
  { id: "scan-results", label: "Scan Results" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminSkillDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [entry, setEntry] = useState<RegistryEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    fetch(`/api/registry/${id}`, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const raw = (await res.json()) as unknown;
        setEntry(mapSnakeToCamel<RegistryEntry>(raw as Record<string, unknown>));
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load skill");
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="text-gray-400 text-sm py-8">Loading skill...</div>;
  }

  if (error || !entry) {
    return (
      <div className="py-8">
        <p className="text-red-600 text-sm mb-4">{error ?? "Skill not found"}</p>
        <Link href="/admin/skills" className="text-sm text-blue-600 hover:underline">
          &larr; Back to Skills
        </Link>
      </div>
    );
  }

  const config = entry.config;
  const securityScore = config.security_score as number | null | undefined;
  const securityReport = config.security_report as SecurityReport | null | undefined;

  const recommendationColor =
    securityReport?.recommendation === "approve"
      ? "bg-green-100 text-green-800"
      : securityReport?.recommendation === "review"
      ? "bg-yellow-100 text-yellow-800"
      : "bg-red-100 text-red-800";

  return (
    <div>
      {/* Breadcrumb */}
      <div className="mb-4">
        <Link href="/admin/skills" className="text-sm text-blue-600 hover:underline">
          &larr; Skills
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
        <div className="flex gap-2 mt-2">
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${
              entry.status === "active"
                ? "bg-green-100 text-green-700"
                : entry.status === "archived"
                ? "bg-gray-100 text-gray-500"
                : entry.status === "pending_review"
                ? "bg-orange-100 text-orange-700"
                : "bg-yellow-100 text-yellow-700"
            }`}
          >
            {entry.status}
          </span>
          <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
            {(config.skill_type as string) ?? "instructional"}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-4">
        <div className="flex gap-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
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

      {/* Tab content */}
      {activeTab === "overview" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-500">ID</dt>
              <dd className="font-mono text-gray-900 text-xs mt-0.5">{entry.id}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Name</dt>
              <dd className="text-gray-900 mt-0.5">{entry.name}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Status</dt>
              <dd className="text-gray-900 mt-0.5">{entry.status}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Owner</dt>
              <dd className="font-mono text-gray-900 text-xs mt-0.5">
                {entry.ownerId ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Created</dt>
              <dd className="text-gray-900 mt-0.5">
                {entry.createdAt ? new Date(entry.createdAt).toLocaleString() : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Updated</dt>
              <dd className="text-gray-900 mt-0.5">
                {entry.updatedAt ? new Date(entry.updatedAt).toLocaleString() : "—"}
              </dd>
            </div>
          </dl>
        </div>
      )}

      {activeTab === "config" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <pre className="text-xs text-gray-700 overflow-auto max-h-96 whitespace-pre-wrap">
            {JSON.stringify(config, null, 2)}
          </pre>
        </div>
      )}

      {activeTab === "scan-results" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          {securityReport == null ? (
            <p className="text-muted-foreground text-sm text-gray-500">
              No scan results available. Use the admin Re-scan button to generate.
            </p>
          ) : (
            <div>
              {/* Score + recommendation */}
              <div className="flex items-center gap-4 mb-6">
                <div>
                  <span className="text-4xl font-bold text-gray-900">
                    {securityScore ?? "—"}
                  </span>
                  <span className="text-gray-400 ml-1">/ 100</span>
                </div>
                {securityReport.recommendation && (
                  <span
                    className={`px-2 py-1 rounded text-sm font-medium ${recommendationColor}`}
                  >
                    {securityReport.recommendation.toUpperCase()}
                  </span>
                )}
                {securityReport.scan_engine && (
                  <span className="text-xs text-gray-400">
                    via {securityReport.scan_engine}
                  </span>
                )}
              </div>

              {/* Bandit issues */}
              <details className="mb-4">
                <summary className="cursor-pointer text-sm font-medium text-gray-700 select-none">
                  Bandit Issues ({securityReport.bandit_issues?.length ?? 0})
                </summary>
                <pre className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-xs overflow-auto max-h-64 text-gray-700">
                  {JSON.stringify(securityReport.bandit_issues ?? [], null, 2)}
                </pre>
              </details>

              {/* pip-audit issues */}
              <details className="mb-4">
                <summary className="cursor-pointer text-sm font-medium text-gray-700 select-none">
                  pip-audit Issues ({securityReport.pip_audit_issues?.length ?? 0})
                </summary>
                <pre className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-xs overflow-auto max-h-64 text-gray-700">
                  {JSON.stringify(securityReport.pip_audit_issues ?? [], null, 2)}
                </pre>
              </details>

              {/* Findings summary */}
              {securityReport.findings && securityReport.findings.length > 0 && (
                <details className="mb-4">
                  <summary className="cursor-pointer text-sm font-medium text-gray-700 select-none">
                    All Findings ({securityReport.findings.length})
                  </summary>
                  <pre className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded text-xs overflow-auto max-h-64 text-gray-700">
                    {JSON.stringify(securityReport.findings, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
