"use client"

/**
 * Settings → Chat Preferences — per-user rendering mode selector.
 *
 * Three rendering modes:
 *   markdown     — Standard ReactMarkdown (default)
 *   card_wrapped — Structured agent responses wrapped in cards
 *   inline_chips — Compact inline chip display for quick facts
 *
 * Selection persists in backend system_config table keyed per-user.
 *
 * CLAUDE.md: `"use client"` for hooks/events; Zod for API validation; no `any`.
 */
import { useState, useEffect } from "react"
import Link from "next/link"
import { z } from "zod"

// ---------------------------------------------------------------------------
// Types and schemas
// ---------------------------------------------------------------------------

const RENDERING_MODES = ["markdown", "card_wrapped", "inline_chips"] as const
type RenderingMode = (typeof RENDERING_MODES)[number]

const PreferencesSchema = z.object({
  rendering_mode: z.enum(RENDERING_MODES).default("markdown"),
})

const MODE_LABELS: Record<RenderingMode, string> = {
  markdown: "Markdown (default)",
  card_wrapped: "Card-wrapped",
  inline_chips: "Inline chips",
}

const MODE_DESCRIPTIONS: Record<RenderingMode, string> = {
  markdown:
    "Responses formatted as standard Markdown — headers, bold, lists, code blocks.",
  card_wrapped:
    "Structured agent outputs (email, calendar, project) render as interactive cards.",
  inline_chips:
    "Key facts and data displayed as compact inline chips within the response.",
}

export default function ChatPreferencesPage() {
  const [renderingMode, setRenderingMode] =
    useState<RenderingMode>("markdown")
  const [loading, setLoading] = useState(true)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    fetch("/api/settings/preferences", { cache: "no-store" })
      .then((r) => r.json())
      .then((raw: unknown) => {
        const parsed = PreferencesSchema.safeParse(raw)
        if (parsed.success) {
          setRenderingMode(parsed.data.rendering_mode)
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  async function handleSave() {
    const res = await fetch("/api/settings/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rendering_mode: renderingMode }),
    })
    if (res.ok) {
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    }
  }

  if (loading) {
    return <div className="p-8 text-gray-500">Loading preferences...</div>
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

      <h1 className="text-2xl font-semibold mb-2">Chat Preferences</h1>
      <p className="text-sm text-gray-500 mb-8">
        Choose how Blitz displays responses in the chat interface.
      </p>

      <fieldset className="space-y-3">
        <legend className="sr-only">Response rendering mode</legend>
        {RENDERING_MODES.map((mode) => (
          <label
            key={mode}
            className={`flex items-start gap-3 p-4 border rounded-lg cursor-pointer transition-colors ${
              renderingMode === mode
                ? "border-blue-400 bg-blue-50"
                : "border-gray-200 hover:border-gray-300 bg-white"
            }`}
          >
            <input
              type="radio"
              name="rendering_mode"
              value={mode}
              checked={renderingMode === mode}
              onChange={() => setRenderingMode(mode)}
              className="mt-0.5 shrink-0"
            />
            <div>
              <p className="text-sm font-medium text-gray-900">
                {MODE_LABELS[mode]}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                {MODE_DESCRIPTIONS[mode]}
              </p>
            </div>
          </label>
        ))}
      </fieldset>

      <div className="mt-8 flex items-center gap-4">
        <button
          onClick={() => void handleSave()}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium transition-colors"
        >
          {saved ? "Saved \u2713" : "Save Preferences"}
        </button>
      </div>
    </main>
  )
}
