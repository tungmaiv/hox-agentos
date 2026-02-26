"use client"

/**
 * EmailSummaryCard — renders EmailSummaryOutput from the email sub-agent.
 *
 * Shows: unread count badge, email rows (from, subject, snippet, time),
 * "Show more" for >5 items, and stub Reply/Archive buttons (disabled in Phase 3).
 * Refresh button calls useMcpTool("email.fetch_unread").
 *
 * Client Component — uses useState for show-all toggle.
 * CLAUDE.md: no `any`; useMcpTool for all tool calls.
 */
import { useState } from "react"
import type { EmailSummaryOutput } from "@/lib/a2ui-types"
import { useMcpTool } from "@/hooks/use-mcp-tool"

interface Props {
  data: EmailSummaryOutput
}

function timeAgo(isoString: string): string {
  try {
    const diff = Date.now() - new Date(isoString).getTime()
    const hours = Math.floor(diff / 3_600_000)
    if (hours < 1) return "just now"
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  } catch {
    return ""
  }
}

export function EmailSummaryCard({ data }: Props) {
  const [showAll, setShowAll] = useState(false)
  const displayItems = showAll ? data.items : data.items.slice(0, 5)

  // Refresh calls the email.fetch_unread tool through useMcpTool.
  // This is a stub in Phase 3 (no real OAuth yet) but the hook wiring is correct.
  const { call: refreshEmails, isLoading } = useMcpTool<
    Record<string, never>,
    unknown
  >("email.fetch_unread")

  // Workaround for the empty-object param: cast to satisfy TS in strict mode
  const handleRefresh = () => { void refreshEmails({} as Record<string, never>) }

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm p-4 my-2 max-w-lg">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">
          Inbox &mdash;{" "}
          <span className="text-blue-600">{data.unread_count} unread</span>
        </h3>
        <button
          onClick={handleRefresh}
          disabled={isLoading}
          className="text-gray-400 hover:text-gray-600 text-xs disabled:opacity-50"
          title="Refresh"
          aria-label="Refresh email list"
        >
          {isLoading ? "..." : "\u21BA"}
        </button>
      </div>

      <div className="space-y-2">
        {displayItems.map((item, idx) => (
          <div
            key={idx}
            className={`p-2 rounded ${item.is_unread ? "bg-blue-50" : ""}`}
          >
            <div className="flex justify-between items-start">
              <span className="text-xs text-gray-500 truncate max-w-[120px]">
                {item.from_}
              </span>
              <span className="text-xs text-gray-400 ml-2 shrink-0">
                {timeAgo(item.received_at)}
              </span>
            </div>
            <p
              className={`text-sm ${
                item.is_unread ? "font-medium" : ""
              } text-gray-800`}
            >
              {item.subject}
            </p>
            <p className="text-xs text-gray-500 truncate">
              {item.snippet.slice(0, 120)}
            </p>
            {/* Reply/Archive are stubs in Phase 3 — rendered disabled */}
            <div className="flex gap-2 mt-1">
              <button
                disabled
                className="text-xs text-gray-300 cursor-not-allowed"
                aria-label="Reply (not yet available)"
              >
                Reply
              </button>
              <button
                disabled
                className="text-xs text-gray-300 cursor-not-allowed"
                aria-label="Archive (not yet available)"
              >
                Archive
              </button>
            </div>
          </div>
        ))}
      </div>

      {data.items.length > 5 && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          className="mt-2 text-xs text-blue-600 hover:underline"
        >
          Show {data.items.length - 5} more
        </button>
      )}
    </div>
  )
}
