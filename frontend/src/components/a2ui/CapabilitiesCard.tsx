"use client"

/**
 * CapabilitiesCard — renders the system.capabilities A2UI response.
 *
 * Shows four collapsible sections (Agents, Tools, Skills, MCP Servers),
 * each with a count badge. Sections are collapsed by default and expand
 * on click. Each item shows display_name (or name) and a one-line description.
 *
 * Per CONTEXT.md locked decisions:
 * - A2UI interactive card — not plain markdown
 * - Collapsed sections with count badges (four sections, collapsed by default)
 * - Static list — names + one-line descriptions, no clickable sub-items
 *
 * CLAUDE.md: "use client" required (uses useState for collapse/expand).
 * No `any`; strict TypeScript; Tailwind only.
 */
import { useState } from "react"
import type { AgentInfo, ToolInfo, SkillInfo, McpServerInfo } from "@/lib/a2ui-types"

interface CapabilitiesCardProps {
  agents: AgentInfo[]
  tools: ToolInfo[]
  skills: SkillInfo[]
  mcp_servers: McpServerInfo[]
  summary: string
}

interface SectionProps {
  label: string
  icon: string
  count: number
  children: React.ReactNode
}

function Section({ label, icon, count, children }: SectionProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-gray-100 rounded-md overflow-hidden">
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm">{icon}</span>
          <span className="text-sm font-medium text-gray-700">{label}</span>
          <span className="ml-1 inline-flex items-center justify-center px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs font-semibold min-w-[20px]">
            {count}
          </span>
        </div>
        <span className="text-gray-400 text-xs">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <div className="divide-y divide-gray-50">
          {children}
        </div>
      )}
    </div>
  )
}

function AgentRow({ item }: { item: AgentInfo }) {
  return (
    <div className="px-3 py-2">
      <div className="text-sm font-medium text-gray-800">
        {item.display_name ?? item.name}
      </div>
      {item.description && (
        <div className="text-xs text-gray-500 mt-0.5 truncate">{item.description}</div>
      )}
    </div>
  )
}

function ToolRow({ item }: { item: ToolInfo }) {
  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-800">
          {item.display_name ?? item.name}
        </span>
        <span className="text-xs px-1 py-0.5 bg-gray-100 text-gray-500 rounded font-mono">
          {item.handler_type}
        </span>
      </div>
      {item.description && (
        <div className="text-xs text-gray-500 mt-0.5 truncate">{item.description}</div>
      )}
    </div>
  )
}

function SkillRow({ item }: { item: SkillInfo }) {
  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-800">
          {item.display_name ?? item.name}
        </span>
        {item.slash_command && (
          <span className="text-xs px-1 py-0.5 bg-indigo-50 text-indigo-600 rounded font-mono">
            {item.slash_command}
          </span>
        )}
      </div>
      {item.description && (
        <div className="text-xs text-gray-500 mt-0.5 truncate">{item.description}</div>
      )}
    </div>
  )
}

function McpServerRow({ item }: { item: McpServerInfo }) {
  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-800">
          {item.display_name ?? item.name}
        </span>
        <span className="text-xs text-gray-400">
          {item.tools_count} {item.tools_count === 1 ? "tool" : "tools"}
        </span>
      </div>
    </div>
  )
}

export function CapabilitiesCard({
  agents,
  tools,
  skills,
  mcp_servers,
  summary,
}: CapabilitiesCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm p-4 my-2 max-w-lg">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm">&#128295;</span>
        <h3 className="text-sm font-semibold text-gray-700">System Capabilities</h3>
      </div>
      <p className="text-xs text-gray-500 mb-3">{summary}</p>

      <div className="space-y-2">
        <Section label="Agents" icon="&#129302;" count={agents.length}>
          {agents.length === 0 ? (
            <div className="px-3 py-2 text-xs text-gray-400">No agents registered.</div>
          ) : (
            agents.map((agent, idx) => <AgentRow key={idx} item={agent} />)
          )}
        </Section>

        <Section label="Tools" icon="&#128295;" count={tools.length}>
          {tools.length === 0 ? (
            <div className="px-3 py-2 text-xs text-gray-400">No tools registered.</div>
          ) : (
            tools.map((tool, idx) => <ToolRow key={idx} item={tool} />)
          )}
        </Section>

        <Section label="Skills" icon="&#127775;" count={skills.length}>
          {skills.length === 0 ? (
            <div className="px-3 py-2 text-xs text-gray-400">No skills registered.</div>
          ) : (
            skills.map((skill, idx) => <SkillRow key={idx} item={skill} />)
          )}
        </Section>

        <Section label="MCP Servers" icon="&#128279;" count={mcp_servers.length}>
          {mcp_servers.length === 0 ? (
            <div className="px-3 py-2 text-xs text-gray-400">No MCP servers registered.</div>
          ) : (
            mcp_servers.map((server, idx) => <McpServerRow key={idx} item={server} />)
          )}
        </Section>
      </div>
    </div>
  )
}
