/**
 * Zod schemas and TypeScript types for A2UI structured agent outputs.
 *
 * These schemas are the frontend counterpart of backend/core/schemas/agent_outputs.py.
 * Used by A2UIMessageRenderer to validate and route JSON agent responses to
 * the correct card component.
 *
 * CLAUDE.md: Zod for all external data validation; no `any`; strict TypeScript.
 */
import { z } from "zod"

// ---------------------------------------------------------------------------
// Calendar
// ---------------------------------------------------------------------------

export const CalendarEventSchema = z.object({
  title: z.string(),
  start_time: z.string(),
  end_time: z.string(),
  location: z.string().nullable().optional(),
  has_conflict: z.boolean().default(false),
})

export const CalendarOutputSchema = z.object({
  agent: z.literal("calendar"),
  date: z.string(),
  events: z.array(CalendarEventSchema),
})

// ---------------------------------------------------------------------------
// Email
// ---------------------------------------------------------------------------

export const EmailSummaryItemSchema = z.object({
  from_: z.string(),
  subject: z.string(),
  received_at: z.string(),
  snippet: z.string(),
  is_unread: z.boolean(),
})

export const EmailSummaryOutputSchema = z.object({
  agent: z.literal("email"),
  unread_count: z.number(),
  items: z.array(EmailSummaryItemSchema),
})

// ---------------------------------------------------------------------------
// Project Status
// ---------------------------------------------------------------------------

export const ProjectStatusResultSchema = z.object({
  agent: z.literal("project"),
  project_name: z.string(),
  status: z.enum(["active", "on-hold", "completed"]),
  owner: z.string(),
  progress_pct: z.number().min(0).max(100),
  last_update: z.string(),
})

// ---------------------------------------------------------------------------
// TypeScript types (inferred from schemas)
// ---------------------------------------------------------------------------

export type CalendarEvent = z.infer<typeof CalendarEventSchema>
export type CalendarOutput = z.infer<typeof CalendarOutputSchema>
export type EmailSummaryItem = z.infer<typeof EmailSummaryItemSchema>
export type EmailSummaryOutput = z.infer<typeof EmailSummaryOutputSchema>
export type ProjectStatusResult = z.infer<typeof ProjectStatusResultSchema>
