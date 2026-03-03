// frontend/src/app/admin/config/page.tsx
"use client";

/**
 * Admin Config page — agent enable/disable toggles.
 *
 * Lives at /admin/config (part of the unified admin dashboard).
 * Admin layout provides the nav, padding, and role gate — no back-link needed here.
 *
 * Toggle state persists across reloads via PUT /api/admin/config/{key}.
 */

import { useEffect, useState } from "react";
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

export default function AdminConfigPage() {
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
    return <div className="text-gray-500 py-8">Loading agent settings...</div>;
  }

  if (loadState === "forbidden") {
    return (
      <div className="py-8">
        <p className="text-red-600">
          Admin access required. Contact your IT administrator to manage agent
          settings.
        </p>
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <div className="py-8">
        <p className="text-red-600">
          Failed to load agent settings. Please try again.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-6">System Configuration</h2>

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
    </div>
  );
}
