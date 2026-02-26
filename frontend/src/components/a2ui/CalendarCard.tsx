/**
 * CalendarCard — renders CalendarOutput from the calendar sub-agent.
 *
 * Shows: date header, event rows with time + title + optional location,
 * and a red "Conflict" badge on events with has_conflict=true.
 *
 * Server Component (no hooks, no browser events).
 * CLAUDE.md: no `any`; strict TypeScript; Tailwind only.
 */
import type { CalendarOutput, CalendarEvent } from "@/lib/a2ui-types"

interface Props {
  data: CalendarOutput
}

function formatTime(isoString: string): string {
  try {
    return new Date(isoString).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return isoString
  }
}

function EventRow({ event }: { event: CalendarEvent }) {
  return (
    <div className="py-2 border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500 min-w-[100px] shrink-0">
          {formatTime(event.start_time)} &ndash; {formatTime(event.end_time)}
        </span>
        <span className="text-sm font-medium text-gray-900 flex-1">
          {event.title}
        </span>
        {event.has_conflict && (
          <span className="ml-auto px-1.5 py-0.5 bg-red-100 text-red-700 text-xs rounded font-medium shrink-0">
            Conflict
          </span>
        )}
      </div>
      {event.location && (
        <p className="text-xs text-gray-400 mt-0.5 ml-[108px]">
          {event.location}
        </p>
      )}
    </div>
  )
}

export function CalendarCard({ data }: Props) {
  const dateLabel = new Date(data.date).toLocaleDateString([], {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  })

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm p-4 my-2 max-w-lg">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{dateLabel}</h3>
      {data.events.length === 0 ? (
        <p className="text-sm text-gray-400">No events today.</p>
      ) : (
        <div>
          {data.events.map((event, idx) => (
            <EventRow key={idx} event={event} />
          ))}
        </div>
      )}
    </div>
  )
}
