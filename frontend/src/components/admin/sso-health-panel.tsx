"use client";
/**
 * SSO Health Panel — 4-card diagnostic dashboard with circuit breaker status
 * and threshold configuration.
 *
 * Renders at the top of the Identity admin page. Shows real-time SSO health
 * across 4 categories: Certificate, Config, Connectivity, Performance.
 *
 * Uses the useSSOHealth hook for data fetching, auto-refresh, and mutations.
 */
import { useState } from "react";
import { Shield, Settings, Wifi, Zap, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { useSSOHealth } from "@/hooks/use-sso-health";
import type { SSOHealthCategory } from "@/lib/api-types";

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  green: "bg-green-500",
  yellow: "bg-yellow-500",
  red: "bg-red-500",
};

const STATUS_BG: Record<string, string> = {
  green: "bg-green-50 border-green-200",
  yellow: "bg-yellow-50 border-yellow-200",
  red: "bg-red-50 border-red-200",
};

const CATEGORY_ICONS: Record<string, typeof Shield> = {
  certificate: Shield,
  config: Settings,
  connectivity: Wifi,
  performance: Zap,
};

const CB_STATE_COLORS: Record<string, string> = {
  closed: "bg-green-100 text-green-800",
  "half-open": "bg-yellow-100 text-yellow-800",
  half_open: "bg-yellow-100 text-yellow-800",
  open: "bg-red-100 text-red-800",
};

function CategoryCard({ category }: { category: SSOHealthCategory }) {
  const Icon = CATEGORY_ICONS[category.name] ?? Settings;
  const dotColor = STATUS_COLORS[category.status] ?? "bg-gray-400";
  const bgColor = STATUS_BG[category.status] ?? "bg-gray-50 border-gray-200";

  return (
    <div className={`rounded-lg border p-4 shadow-sm ${bgColor}`}>
      <div className="flex items-center gap-3">
        <Icon className="h-5 w-5 text-gray-600 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={`inline-block h-2.5 w-2.5 rounded-full ${dotColor}`} />
            <span className="text-sm font-medium text-gray-900 capitalize">
              {category.name}
            </span>
          </div>
          <p className="mt-1 text-xs text-gray-600 truncate" title={category.detail}>
            {category.detail}
          </p>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Threshold config section
// ---------------------------------------------------------------------------

function ThresholdConfig({
  initialThresholds,
  cbState,
  onSave,
  onReset,
}: {
  initialThresholds: { failure_threshold: number; recovery_timeout_seconds: number; half_open_max_calls: number };
  cbState: string;
  onSave: (t: { failure_threshold: number; recovery_timeout_seconds: number; half_open_max_calls: number }) => Promise<boolean>;
  onReset: () => Promise<boolean>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [failureThreshold, setFailureThreshold] = useState(initialThresholds.failure_threshold);
  const [recoveryTimeout, setRecoveryTimeout] = useState(initialThresholds.recovery_timeout_seconds);
  const [halfOpenMaxCalls, setHalfOpenMaxCalls] = useState(initialThresholds.half_open_max_calls);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [saveResult, setSaveResult] = useState<"success" | "error" | null>(null);

  const isValid =
    failureThreshold >= 1 &&
    recoveryTimeout >= 5 &&
    halfOpenMaxCalls >= 1 &&
    Number.isInteger(failureThreshold) &&
    Number.isInteger(recoveryTimeout) &&
    Number.isInteger(halfOpenMaxCalls);

  const showResetButton = cbState === "open" || cbState === "half-open" || cbState === "half_open";

  async function handleSave() {
    setSaving(true);
    setSaveResult(null);
    const ok = await onSave({
      failure_threshold: failureThreshold,
      recovery_timeout_seconds: recoveryTimeout,
      half_open_max_calls: halfOpenMaxCalls,
    });
    setSaveResult(ok ? "success" : "error");
    setSaving(false);
    if (ok) {
      setTimeout(() => setSaveResult(null), 3000);
    }
  }

  async function handleReset() {
    setResetting(true);
    await onReset();
    setResetting(false);
  }

  return (
    <div className="mt-4">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-sm font-medium text-gray-700 hover:text-gray-900"
      >
        {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        Configure Thresholds
      </button>

      {expanded && (
        <div className="mt-3 space-y-4 rounded-md border border-gray-200 bg-gray-50 p-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="failure_threshold" className="block text-xs font-medium text-gray-600">
                Failure Threshold
              </label>
              <input
                id="failure_threshold"
                type="number"
                min={1}
                step={1}
                value={failureThreshold}
                onChange={(e) => setFailureThreshold(parseInt(e.target.value, 10) || 1)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="recovery_timeout" className="block text-xs font-medium text-gray-600">
                Recovery Timeout (s)
              </label>
              <input
                id="recovery_timeout"
                type="number"
                min={5}
                step={1}
                value={recoveryTimeout}
                onChange={(e) => setRecoveryTimeout(parseInt(e.target.value, 10) || 5)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="half_open_max" className="block text-xs font-medium text-gray-600">
                Max Half-Open Calls
              </label>
              <input
                id="half_open_max"
                type="number"
                min={1}
                step={1}
                value={halfOpenMaxCalls}
                onChange={(e) => setHalfOpenMaxCalls(parseInt(e.target.value, 10) || 1)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={!isValid || saving}
              onClick={() => void handleSave()}
              className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Saving..." : "Save Thresholds"}
            </button>

            {showResetButton && (
              <button
                type="button"
                disabled={resetting}
                onClick={() => void handleReset()}
                className="rounded-md border border-gray-300 bg-white px-4 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-60"
              >
                {resetting ? "Resetting..." : "Reset Circuit Breaker"}
              </button>
            )}

            {saveResult === "success" && (
              <span className="text-sm text-green-700">Thresholds saved</span>
            )}
            {saveResult === "error" && (
              <span className="text-sm text-red-700">Failed to save</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export default function SSOHealthPanel() {
  const { health, loading, error, refresh, updateThresholds, resetCircuitBreaker } =
    useSSOHealth();
  const [refreshing, setRefreshing] = useState(false);

  async function handleRefresh() {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  }

  if (loading && !health) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-gray-500">Loading SSO health diagnostics...</p>
      </div>
    );
  }

  if (error && !health) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 shadow-sm">
        <p className="text-sm text-red-700">
          Failed to load SSO health: {error}
        </p>
      </div>
    );
  }

  if (!health) return null;

  const borderTop =
    health.overall === "unhealthy"
      ? "border-t-4 border-t-red-500"
      : health.overall === "degraded"
      ? "border-t-4 border-t-yellow-500"
      : "";

  const cbState = health.circuit_breaker.state.toLowerCase();
  const cbColor = CB_STATE_COLORS[cbState] ?? "bg-gray-100 text-gray-800";

  const checkedAt = new Date(health.checked_at);
  const secondsAgo = Math.max(0, Math.floor((Date.now() - checkedAt.getTime()) / 1000));

  return (
    <div className={`rounded-lg border border-gray-200 bg-white p-6 shadow-sm ${borderTop}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-medium text-gray-900">SSO Health Monitor</h3>
          <p className="text-xs text-gray-500">
            Real-time diagnostics for Keycloak SSO integration
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">
            Last checked: {secondsAgo < 60 ? `${secondsAgo}s ago` : `${Math.floor(secondsAgo / 60)}m ago`}
          </span>
          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={refreshing}
            className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-60"
          >
            <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* 4 diagnostic cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {health.categories.map((cat) => (
          <CategoryCard key={cat.name} category={cat} />
        ))}
      </div>

      {/* Circuit breaker status bar */}
      <div className="mt-4 flex items-center gap-3 text-sm">
        <span className="text-gray-600">Circuit Breaker:</span>
        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cbColor}`}>
          {health.circuit_breaker.state.toUpperCase()}
        </span>
        <span className="text-xs text-gray-500">
          Failures: {health.circuit_breaker.failure_count}
        </span>
      </div>

      {/* Threshold configuration */}
      <ThresholdConfig
        initialThresholds={health.circuit_breaker.thresholds}
        cbState={cbState}
        onSave={updateThresholds}
        onReset={resetCircuitBreaker}
      />
    </div>
  );
}
