/**
 * Server-side proxy for user chat preferences.
 *
 * GET → backend GET /api/user/preferences
 * PUT → backend PUT /api/user/preferences
 *
 * Bearer token injected server-side — never sent to browser.
 * CLAUDE.md: use `auth()` from next-auth v5; NEXT_PUBLIC_API_URL.
 */
import { auth } from "@/auth"
import { NextRequest, NextResponse } from "next/server"

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
    const res = await fetch(`${API_URL}/api/user/preferences`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    })
    const data: unknown = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json(
      { rendering_mode: "markdown" },
      { status: 500 }
    )
  }
}

export async function PUT(request: NextRequest): Promise<NextResponse> {
  const accessToken = await getAccessToken()
  if (!accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const body: unknown = await request.json()
    const res = await fetch(`${API_URL}/api/user/preferences`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    })
    const data: unknown = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json(
      { error: "Failed to update preferences" },
      { status: 500 }
    )
  }
}
