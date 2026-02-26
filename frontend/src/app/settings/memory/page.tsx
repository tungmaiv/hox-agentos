"use client"

/**
 * Settings → Memory — per-user transparency view of stored facts and episodes.
 *
 * "Data about me" design philosophy: users can see exactly what Blitz remembers
 * and delete any or all of it.
 *
 * Features:
 * - List of active memory facts with source and creation date
 * - Delete individual fact (soft-delete via backend)
 * - "Clear all memory" button with confirmation dialog
 * - Collapsible episode summaries section
 *
 * CLAUDE.md: `"use client"` for hooks/events; Zod for API validation; no `any`.
 */
import { useState, useEffect } from "react"
import Link from "next/link"
import { z } from "zod"

// ---------------------------------------------------------------------------
// Zod schemas for API response validation
// ---------------------------------------------------------------------------

const FactSchema = z.object({
  id: z.string(),
  content: z.string(),
  source: z.string().nullable(),
  created_at: z.string(),
})

const EpisodeSchema = z.object({
  id: z.string(),
  summary: z.string(),
  created_at: z.string(),
})

const MemoryResponseSchema = z.object({
  facts: z.array(FactSchema),
  episodes: z.array(EpisodeSchema),
})

type Fact = z.infer<typeof FactSchema>
type Episode = z.infer<typeof EpisodeSchema>

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString([], {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
  } catch {
    return iso
  }
}

export default function MemorySettingsPage() {
  const [facts, setFacts] = useState<Fact[]>([])
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [loading, setLoading] = useState(true)
  const [episodesExpanded, setEpisodesExpanded] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  async function loadMemory() {
    setLoading(true)
    try {
      const res = await fetch("/api/settings/memory", { cache: "no-store" })
      if (!res.ok) {
        setLoading(false)
        return
      }
      const raw: unknown = await res.json()
      const parsed = MemoryResponseSchema.safeParse(raw)
      if (parsed.success) {
        setFacts(parsed.data.facts)
        setEpisodes(parsed.data.episodes)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadMemory()
  }, [])

  async function handleDeleteFact(factId: string) {
    const res = await fetch(`/api/settings/memory/${factId}`, {
      method: "DELETE",
    })
    if (res.ok) {
      setFacts((prev) => prev.filter((f) => f.id !== factId))
      setActionMessage("Fact deleted.")
      setTimeout(() => setActionMessage(null), 2000)
    }
  }

  async function handleClearAll() {
    const res = await fetch("/api/settings/memory", { method: "DELETE" })
    if (res.ok) {
      setFacts([])
      setConfirmClear(false)
      setActionMessage("All memory cleared.")
      setTimeout(() => setActionMessage(null), 2000)
    }
  }

  if (loading) {
    return <div className="p-8 text-gray-500">Loading memory...</div>
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

      <h1 className="text-2xl font-semibold mb-2">Memory</h1>
      <p className="text-sm text-gray-500 mb-6">
        This is what Blitz remembers about you. You can delete individual facts
        or clear everything.
      </p>

      {/* Action feedback */}
      {actionMessage && (
        <div className="mb-4 px-3 py-2 bg-green-50 border border-green-200 rounded text-sm text-green-700">
          {actionMessage}
        </div>
      )}

      {/* Clear all section */}
      <div className="flex items-center justify-between mb-6">
        <span className="text-sm text-gray-600">
          {facts.length} stored {facts.length === 1 ? "fact" : "facts"}
        </span>
        {facts.length > 0 && !confirmClear && (
          <button
            onClick={() => setConfirmClear(true)}
            className="text-sm text-red-600 hover:underline"
          >
            Clear all memory
          </button>
        )}
        {confirmClear && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Are you sure?</span>
            <button
              onClick={() => void handleClearAll()}
              className="text-sm text-red-600 font-medium hover:underline"
            >
              Yes, clear all
            </button>
            <button
              onClick={() => setConfirmClear(false)}
              className="text-sm text-gray-500 hover:underline"
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {/* Facts list */}
      {facts.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">
          No stored facts yet. Blitz will remember things you tell it during
          conversations.
        </p>
      ) : (
        <ul className="space-y-2 mb-8">
          {facts.map((fact) => (
            <li
              key={fact.id}
              className="flex items-start justify-between p-3 border border-gray-200 rounded-lg bg-white"
            >
              <div className="flex-1 min-w-0 pr-4">
                <p className="text-sm text-gray-900">{fact.content}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {fact.source ? `From: ${fact.source} · ` : ""}
                  {formatDate(fact.created_at)}
                </p>
              </div>
              <button
                onClick={() => void handleDeleteFact(fact.id)}
                className="text-xs text-red-500 hover:text-red-700 shrink-0"
                aria-label={`Delete fact: ${fact.content.slice(0, 40)}`}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Episodes section (collapsible) */}
      {episodes.length > 0 && (
        <section>
          <button
            onClick={() => setEpisodesExpanded(!episodesExpanded)}
            className="flex items-center gap-1 text-sm font-medium text-gray-700 hover:text-gray-900 mb-3"
            aria-expanded={episodesExpanded}
          >
            <span>{episodesExpanded ? "▼" : "▶"}</span>
            Conversation summaries ({episodes.length})
          </button>
          {episodesExpanded && (
            <ul className="space-y-2">
              {episodes.map((ep) => (
                <li
                  key={ep.id}
                  className="p-3 border border-gray-200 rounded-lg bg-gray-50"
                >
                  <p className="text-sm text-gray-700">{ep.summary}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {formatDate(ep.created_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  )
}
