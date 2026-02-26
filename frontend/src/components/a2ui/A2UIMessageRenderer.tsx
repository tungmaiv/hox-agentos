"use client"

/**
 * A2UIMessageRenderer — universal message renderer for chat assistant messages.
 *
 * Routing logic:
 *   1. If role is "user" → render plain whitespace-preserving text
 *   2. If content is JSON with `agent` field → route to matching card component
 *      - agent="calendar" → CalendarCard (with Zod validation)
 *      - agent="email" → EmailSummaryCard (with Zod validation)
 *      - agent="project" → ProjectStatusWidget (with Zod validation)
 *   3. Fallback → ReactMarkdown rendering
 *
 * All Zod safeParse calls must succeed silently — no errors thrown on parse
 * failure, fallback to ReactMarkdown instead.
 *
 * CLAUDE.md: `"use client"` required (uses react-markdown which is client-only).
 * No `any`; use `unknown` and narrow.
 */
import {
  CalendarOutputSchema,
  EmailSummaryOutputSchema,
  ProjectStatusResultSchema,
} from "@/lib/a2ui-types"
import { CalendarCard } from "./CalendarCard"
import { EmailSummaryCard } from "./EmailSummaryCard"
import { ProjectStatusWidget } from "./ProjectStatusWidget"
import ReactMarkdown from "react-markdown"

interface Props {
  content: string
  role: "user" | "assistant"
}

export function A2UIMessageRenderer({ content, role }: Props) {
  // User messages: render plain text preserving whitespace
  if (role !== "assistant") {
    return <div className="whitespace-pre-wrap">{content}</div>
  }

  // Attempt to parse as A2UI structured output
  try {
    const parsed: unknown = JSON.parse(content)
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "agent" in parsed
    ) {
      const agentType = (parsed as Record<string, unknown>).agent

      if (agentType === "calendar") {
        const result = CalendarOutputSchema.safeParse(parsed)
        if (result.success) {
          return <CalendarCard data={result.data} />
        }
      }

      if (agentType === "email") {
        const result = EmailSummaryOutputSchema.safeParse(parsed)
        if (result.success) {
          return <EmailSummaryCard data={result.data} />
        }
      }

      if (agentType === "project") {
        const result = ProjectStatusResultSchema.safeParse(parsed)
        if (result.success) {
          return <ProjectStatusWidget data={result.data} />
        }
      }
    }
  } catch {
    // Not JSON — fall through to markdown rendering
  }

  // Fallback: render as markdown
  // react-markdown v10 does not accept className directly; wrap in a div instead.
  return (
    <div className="prose prose-sm max-w-none">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}
