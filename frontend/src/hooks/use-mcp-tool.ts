"use client"

/**
 * useMcpTool — universal hook for all UI-initiated tool/MCP calls.
 *
 * Per CONTEXT.md: this is the ONLY way A2UI components call tools.
 * No component calls fetch() directly — always through this hook.
 *
 * The hook POSTs to /api/tools/call (Next.js proxy route), which injects
 * the server-side Bearer token and forwards to backend POST /api/tools/call.
 *
 * CLAUDE.md: no `any`; use `unknown` and narrow; strict TypeScript.
 */
import { useState, useCallback } from "react"

export interface UseMcpToolResult<TParams, TResult> {
  call: (params: TParams) => Promise<TResult | null>
  isLoading: boolean
  error: string | null
}

export function useMcpTool<TParams, TResult>(
  toolName: string
): UseMcpToolResult<TParams, TResult> {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const call = useCallback(
    async (params: TParams): Promise<TResult | null> => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await fetch("/api/tools/call", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tool: toolName, params }),
        })
        if (!response.ok) {
          const errorData: unknown = await response.json()
          const message =
            typeof errorData === "object" &&
            errorData !== null &&
            "detail" in errorData
              ? String((errorData as Record<string, unknown>).detail)
              : `Request failed: ${response.status}`
          setError(message)
          return null
        }
        const data: unknown = await response.json()
        return data as TResult
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Unknown error"
        setError(message)
        return null
      } finally {
        setIsLoading(false)
      }
    },
    [toolName]
  )

  return { call, isLoading, error }
}
