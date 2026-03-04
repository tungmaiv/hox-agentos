/**
 * Server-side proxy for memory settings API.
 *
 * GET  → backend GET /api/user/memory/facts + GET /api/user/memory/episodes
 *        Returns { facts: [...], episodes: [...] }
 * DELETE → backend DELETE /api/user/memory/facts (clear all)
 *
 * Bearer token injected server-side — never sent to browser.
 * CLAUDE.md: use `auth()` from next-auth v5; NEXT_PUBLIC_API_URL.
 */
import { auth } from "@/auth"
import { NextResponse } from "next/server"

const API_URL = process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function getAccessToken(): Promise<string | undefined> {
  const session = await auth()
  return (session as unknown as Record<string, unknown>)
    ?.accessToken as string | undefined
}

export async function GET(): Promise<NextResponse> {
  const accessToken = await getAccessToken()
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const [factsRes, episodesRes] = await Promise.all([
      fetch(`${API_URL}/api/user/memory/facts`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        cache: "no-store",
      }),
      fetch(`${API_URL}/api/user/memory/episodes`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        cache: "no-store",
      }),
    ])

    const [facts, episodes] = await Promise.all([
      factsRes.ok ? factsRes.json() : [],
      episodesRes.ok ? episodesRes.json() : [],
    ])

    return NextResponse.json({ facts, episodes })
  } catch {
    return NextResponse.json(
      { facts: [], episodes: [] },
      { status: 500 }
    )
  }
}

export async function DELETE(): Promise<NextResponse> {
  const accessToken = await getAccessToken()
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const res = await fetch(`${API_URL}/api/user/memory/facts`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    const data: unknown = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json(
      { error: "Failed to clear memory" },
      { status: 500 }
    )
  }
}
