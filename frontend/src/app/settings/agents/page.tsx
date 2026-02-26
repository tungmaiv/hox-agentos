// frontend/src/app/settings/agents/page.tsx
"use client";

/**
 * Admin-only Settings → Agents page.
 * Displays toggle switches for Email, Calendar, and Project agent enable flags.
 * Toggle state persists across reloads via PUT /api/admin/config/{key}.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { z } from "zod";

const AgentConfigSchema = z
  .object({
    "agent.email.enabled": z.boolean().optional(),
    "agent.calendar.enabled": z.boolean().optional(),
    "agent.project.enabled": z.boolean().optional(),
  })
  .passthrough();

type AgentConfig = z.infer<typeof AgentConfigSchema>;

interface AgentToggle {
  key: keyof Pick<
    AgentConfig,
    "agent.email.enabled" | "agent.calendar.enabled" | "agent.project.enabled"
  >;
  label: string;
  description: string;
}

const AGENT_TOGGLES: AgentToggle[] = [
  {
    key: "agent.email.enabled",
    label: "Email Agent",
    description: "Enables email fetching, summarization, and drafting tools.",
  },
  {
    key: "agent.calendar.enabled",
    label: "Calendar Agent",
    description: "Enables calendar lookup and event management tools.",
  },
  {
    key: "agent.project.enabled",
    label: "Project Agent",
    description: "Enables project status and task management tools.",
  },
];

type LoadState = "loading" | "forbidden" | "error" | "ready";

export default function AgentsSettingsPage() {
  const [config, setConfig] = useState<AgentConfig>({});
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/config", { cache: "no-store" })
      .then(async (res) => {
        if (res.status === 403) {
          setLoadState("forbidden");
          return;
        }
        if (!res.ok) {
          setLoadState("error");
          return;
        }
        const raw: unknown = await res.json();
        const parsed = AgentConfigSchema.safeParse(raw);
        if (parsed.success) {
          setConfig(parsed.data);
        }
        setLoadState("ready");
      })
      .catch(() => setLoadState("error"));
  }, []);

  async function handleToggle(key: AgentToggle["key"], newValue: boolean) {
    setSaving(key);
    try {
      const res = await fetch(`/api/admin/config/${encodeURIComponent(key)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: newValue }),
      });
      if (res.ok) {
        setConfig((prev) => ({ ...prev, [key]: newValue }));
      }
    } finally {
      setSaving(null);
    }
  }

  if (loadState === "loading") {
    return <div className="p-8 text-gray-500">Loading agent settings...</div>;
  }

  if (loadState === "forbidden") {
    return (
      <main className="max-w-2xl mx-auto p-8">
        <div className="mb-6">
          <Link
            href="/settings"
            className="text-sm text-blue-600 hover:underline"
          >
            &larr; Back to Settings
          </Link>
        </div>
        <h1 className="text-2xl font-semibold mb-4">Agent Settings</h1>
        <p className="text-red-600">
          Admin access required. Contact your IT administrator to manage agent
          settings.
        </p>
      </main>
    );
  }

  if (loadState === "error") {
    return (
      <main className="max-w-2xl mx-auto p-8">
        <div className="mb-6">
          <Link
            href="/settings"
            className="text-sm text-blue-600 hover:underline"
          >
            &larr; Back to Settings
          </Link>
        </div>
        <h1 className="text-2xl font-semibold mb-4">Agent Settings</h1>
        <p className="text-red-600">
          Failed to load agent settings. Please try again.
        </p>
      </main>
    );
  }

  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="mb-6">
        <Link
          href="/settings"
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; Back to Settings
        </Link>
      </div>

      <h1 className="text-2xl font-semibold mb-2">Agent Settings</h1>
      <p className="text-sm text-gray-500 mb-8">
        Enable or disable individual AI agents. Disabled agents are excluded
        from tool routing. Changes take effect immediately.
      </p>

      <section className="space-y-6">
        {AGENT_TOGGLES.map(({ key, label, description }) => {
          const isEnabled = config[key] ?? true;
          const isSaving = saving === key;

          return (
            <div
              key={key}
              className="flex items-start justify-between p-4 border border-gray-200 rounded-lg bg-white"
            >
              <div className="flex-1 mr-4">
                <h3 className="text-base font-medium text-gray-900">{label}</h3>
                <p className="text-sm text-gray-500 mt-1">{description}</p>
              </div>
              <button
                role="switch"
                aria-checked={isEnabled}
                aria-label={`Toggle ${label}`}
                disabled={isSaving}
                onClick={() => void handleToggle(key, !isEnabled)}
                className={[
                  "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent",
                  "transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2",
                  isSaving ? "opacity-50 cursor-not-allowed" : "",
                  isEnabled ? "bg-blue-600" : "bg-gray-200",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span
                  aria-hidden="true"
                  className={[
                    "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0",
                    "transition duration-200 ease-in-out",
                    isEnabled ? "translate-x-5" : "translate-x-0",
                  ].join(" ")}
                />
              </button>
            </div>
          );
        })}
      </section>
    </main>
  );
}
